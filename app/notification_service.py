#notification_service.py

from .sms_service import send_sms
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def notify_user_of_transaction(user, account_number, amount, transaction_type, updated_balance=None, reference_number=None):
    if transaction_type == 'deposit':
        sms_message = f"Dear {user} Your account has been credited with {amount} in your {account_number}. New balance is {updated_balance}. Reference number: {reference_number}"
    elif transaction_type == 'withdrawal':
        sms_message = f"Dear {user} Your account has been debited with {amount} in your {account_number}. New balance is {updated_balance}. Reference number: {reference_number}"
    elif transaction_type == 'emi_payment':
        sms_message = f"Dear {user} EMI Payment of {amount} has been recieved in you loan account {account_number}, with Reference number: {reference_number}"
    else:
        sms_message = f"Notification: {transaction_type} of {amount}. Reference number: {reference_number}"
    
     # Add default country code if not present
    mobile_number = user.mobile_number
    if not mobile_number.startswith('+'):
        mobile_number = f"+91{user.mobile_number}"  # Add default country code; replace +91 with your preferred code


    send_sms(mobile_number, sms_message)

def notify_user_of_account_opening(user, account_number):
    logger.debug("notify_user_of_account_opening function called.")
    sms_message = f"Congratulations! {user.first_name} {user.last_name} Your account with number {account_number} has been successfully opened. Welcome aboard!"
    # Add default country code if not present
    mobile_number = user.mobile_number
    if not mobile_number.startswith('+'):
        mobile_number = f"+91{user.mobile_number}"  # Add default country code; replace +91 with your preferred code


    send_sms(mobile_number, sms_message)