from flask import render_template, request, redirect, url_for, flash
from .models import Users, Account, Transactions
from . import db
from app import encrypt, decrypt
from datetime import datetime
import random
from .notification_service import notify_user_of_transaction

def generate_random_15_digit_number():
    return random.randint(10**14, 10**15 - 1)

def emi_payment(encrypted_account_number):
    account_number = decrypt(encrypted_account_number)
    user = Users.query.filter_by(account_number=account_number).first()
    if not user:
        flash("User not found", 'error')
        return redirect(url_for('all_accounts'))

    account = Account.query.filter_by(account_number=account_number).first()
    if not account:
        flash("Account not found", 'error')
        return redirect(url_for('all_accounts'))

    # Fetch the latest loan transaction details
    loan_transaction = Transactions.query.filter_by(account_number=account_number).filter(Transactions.loan_amount.isnot(None)).order_by(Transactions.date.desc()).first()
    if not loan_transaction:
        flash("Loan transaction details not found", 'error')
        return redirect(url_for('all_accounts'))

    # Extract loan amount, interest rate, and tenure
    loan_amount = float(loan_transaction.loan_amount)
    interest_rate = float(loan_transaction.interest_rate)  # Convert to decimal
    tenure = int(loan_transaction.tenure)  # Ensure tenure is an integer

    # Calculate EMI
    if interest_rate > 0 and tenure > 0:
        monthly_interest_rate = (interest_rate / 100) / 12
        emi = (loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** tenure) / \
              ((1 + monthly_interest_rate) ** tenure - 1)
    else:
        emi = loan_amount / tenure if tenure > 0 else 0

    emi = round(emi)  # Round EMI to the nearest integer

    if request.method == 'POST':
        try:
            emi_amount = float(request.form['emi_amount'])
            if emi_amount <= 0:
                flash('Invalid EMI amount', 'error')
                return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

            # Fetch the latest transaction to get the current balance
            latest_transaction = Transactions.query.filter_by(account_number=account_number)\
                                                    .order_by(Transactions.date.desc())\
                                                    .first()
            if not latest_transaction:
                flash("No transaction found for the account", 'error')
                return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

            remaining_loan_amount = float(latest_transaction.balance)

            # If the remaining loan amount is less than the EMI, adjust to cover the remaining balance
            if remaining_loan_amount <= emi_amount:
                emi_amount = remaining_loan_amount

            # Update remaining loan amount and account balance
            remaining_loan_amount -= emi_amount
            account.balance = remaining_loan_amount
            db.session.commit()

            # Calculate the interest portion of the EMI for this payment
            interest_payment = round(loan_amount * monthly_interest_rate)
            # Principal payment is EMI minus the interest portion
            principal_payment = emi - interest_payment

            reference_number = generate_random_15_digit_number()

            # Save transaction details
            new_transaction = Transactions(
                account_number=account_number,
                date=datetime.now(),
                description='EMI Payment',
                amount=principal_payment,
                balance=remaining_loan_amount,  # Updated remaining loan amount
                deposit=emi_amount,  # Full EMI payment logged as deposit
                reference_number=reference_number
            )
            db.session.add(new_transaction)
            db.session.commit()

            # Send SMS notification using the utility function
            notify_user_of_transaction(user, emi_amount, 'emi_payment', updated_balance=account.balance, reference_number=reference_number)
            # Success message based on loan closure
            if remaining_loan_amount == 0:
                flash(f'EMI Payment successful. Loan fully paid. Reference number: {reference_number}', 'success')
            else:
                flash(f'EMI Payment successful. Reference number: {reference_number}', 'success')

            return redirect(url_for('all_accounts'))

        except Exception as e:
            print(f"Exception occurred: {str(e)}")
            db.session.rollback()
            flash('Transaction failed. Please try again later.', 'error')
            return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

    return render_template('emi_payment.html', user=user, account=account, remaining_loan_amount=account.balance, emi=emi, encrypt=encrypt)
