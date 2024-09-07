import logging
from flask import render_template, request, redirect, url_for, flash
from .models import Users, Account, Transactions
from . import db
from app import encrypt, decrypt
from datetime import datetime
import random
from .notification_service import notify_user_of_transaction

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_random_15_digit_number():
    return random.randint(10**14, 10**15 - 1)

def emi_payment(encrypted_account_number):
    account_number = decrypt(encrypted_account_number)
    user = Users.query.filter_by(account_number=account_number).first()
    if not user:
        flash("User not found", 'error')
        logging.error(f"User with account number {account_number} not found.")
        return redirect(url_for('all_accounts'))

    account = Account.query.filter_by(account_number=account_number).first()
    if not account:
        flash("Account not found", 'error')
        logging.error(f"Account with account number {account_number} not found.")
        return redirect(url_for('all_accounts'))

    # Fetch the latest loan transaction details
    loan_transaction = Transactions.query.filter_by(account_number=account_number).filter(Transactions.loan_amount.isnot(None)).order_by(Transactions.date.desc()).first()
    if not loan_transaction:
        flash("Loan transaction details not found", 'error')
        logging.error(f"Loan transaction not found for account {account_number}.")
        return redirect(url_for('all_accounts'))

    # Extract loan amount, interest rate, and tenure
    loan_amount = float(loan_transaction.loan_amount)
    interest_rate = float(loan_transaction.interest_rate)
    tenure = int(loan_transaction.tenure)

    # Calculate EMI based on interest rate and tenure
    if interest_rate > 0 and tenure > 0:
        monthly_interest_rate = (interest_rate / 100) / 12
        emi = (loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** tenure) / \
              ((1 + monthly_interest_rate) ** tenure - 1)
    else:
        emi = loan_amount / tenure if tenure > 0 else 0

    emi = round(emi)

    if request.method == 'POST':
        try:
            emi_amount = float(request.form['emi_amount'])
            if emi_amount <= 0:
                flash('Invalid EMI amount', 'error')
                logging.error(f"Invalid EMI amount entered: {emi_amount}.")
                return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

            # Fetch the latest transaction to get the current balance
            latest_transaction = Transactions.query.filter_by(account_number=account_number)\
                                                    .order_by(Transactions.date.desc())\
                                                    .first()
            if not latest_transaction:
                flash("No transaction found for the account", 'error')
                logging.error(f"No previous transactions found for account {account_number}.")
                return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

            remaining_loan_amount = float(latest_transaction.balance)

            # Adjust EMI if the remaining loan amount is less than the EMI
            if remaining_loan_amount < emi_amount:
                emi_amount = remaining_loan_amount

            # Update remaining loan amount and account balance
            remaining_loan_amount -= emi_amount
            account.balance = remaining_loan_amount
            db.session.commit()

            # Calculate the interest portion of the EMI for this payment
            interest_payment = round(loan_amount * monthly_interest_rate)
            # Principal payment is EMI minus the interest portion
            principal_payment = emi_amount - interest_payment

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

            logging.info(f"EMI Payment successful for account {account_number}. Reference number: {reference_number}")

            # Try sending SMS notification
            try:
                notify_user_of_transaction(user, emi_amount, 'emi_payment', updated_balance=account.balance, reference_number=reference_number, transaction_type='emi_payment')
                logging.info(f"Notification sent for account {account_number}.")
            except Exception as e:
                logging.error(f"Failed to send notification for account {account_number}: {str(e)}")
                flash('EMI Payment successful, but notification failed.', 'warning')

            # Success message based on loan closure
            if remaining_loan_amount == 0:
                flash(f'EMI Payment successful. Loan fully paid. Reference number: {reference_number}', 'success')
                logging.info(f"Loan fully paid for account {account_number}.")
            else:
                flash(f'EMI Payment successful. Reference number: {reference_number}', 'success')

            return redirect(url_for('all_accounts'))

        except Exception as e:
            logging.error(f"Exception occurred during EMI payment for account {account_number}: {str(e)}")
            db.session.rollback()
            flash('Transaction failed. Please try again later.', 'error')
            return redirect(url_for('emi_payment', encrypted_account_number=encrypted_account_number))

    return render_template('emi_payment.html', user=user, account=account, remaining_loan_amount=account.balance, emi=emi, encrypt=encrypt)
