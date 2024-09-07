import logging
from flask import render_template, request, redirect, url_for, flash
from .models import Users, Account, Transactions
from . import db
import random
from app import encrypt, decrypt
from functools import wraps
from .notification_service import notify_user_of_transaction

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_random_15_digit_number():
    return random.randint(10**14, 10**15 - 1)

def deposit(encrypted_account_number):
    account_number = decrypt(encrypted_account_number)
    if not account_number:
        flash("Invalid account number", 'error')
        logging.error("Invalid account number provided for deposit.")
        return redirect(url_for('all_accounts'))

    user = Users.query.filter_by(account_number=account_number).first()
    if not user:
        flash("User not found", 'error')
        logging.error(f"User with account number {account_number} not found.")
        return redirect(url_for('all_accounts'))

    account = Account.query.filter_by(account_number=user.account_number).first()
    if not account:
        flash("Account not found", 'error')
        logging.error(f"Account with account number {account_number} not found.")
        return redirect(url_for('all_accounts'))

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            transaction_type = 'Deposit'

            if amount <= 0:
                flash('Invalid deposit amount', 'error')
                logging.error(f"Invalid deposit amount: {amount}. Deposit amount must be positive.")
                return redirect(url_for('deposit', encrypted_account_number=encrypted_account_number))

            # Add the deposited amount to the account's balance
            account.balance += amount
            updated_balance = account.balance
            reference_number = generate_random_15_digit_number()

            # Save transaction details
            new_transaction = Transactions(
                account_number=user.account_number,
                description=f'{transaction_type} of {amount}',
                balance=updated_balance,
                deposit=amount,
                reference_number=reference_number
            )
            db.session.add(new_transaction)
            db.session.commit()

            logging.info(f"Deposit of {amount} successful for account {account_number}. Reference number: {reference_number}")

            # Send SMS notification using the utility function
            try:
                notify_user_of_transaction(user, amount, 'deposit', updated_balance=updated_balance, reference_number=reference_number, transaction_type ='deposit')
                logging.info(f"Notification sent successfully for account {account_number}.")
            except Exception as e:
                logging.error(f"Failed to send notification for account {account_number}: {str(e)}")
                flash('Deposit successful, but notification failed.', 'warning')

            # After committing transaction, redirect with reference number as query parameter
            flash(f'{transaction_type} successful. Reference number: {reference_number}', 'success')
            return redirect(url_for('all_accounts'))

        except Exception as e:
            logging.error(f"Exception occurred during deposit for account {account_number}: {str(e)}")
            db.session.rollback()
            flash('Transaction failed. Please try again later.', 'error')
            return redirect(url_for('deposit', encrypted_account_number=encrypted_account_number))

    return render_template('deposit.html', user=user, account=account, encrypt=encrypt)
