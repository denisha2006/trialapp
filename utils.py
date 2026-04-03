import random
import string
import hashlib
import hmac
import os
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message

bcrypt = Bcrypt()
mail = Mail()

def generate_otp():
    """Generates a 6-digit random OTP."""
    return ''.join(random.choices(string.digits, k=6))

def send_email(to, subject, body, html=None):
    """Sends an email using Flask-Mail. Falls back to console print if not configured."""
    try:
        sender = os.getenv('MAIL_DEFAULT_SENDER')
        msg = Message(subject, recipients=[to], body=body, html=html, sender=sender)
        mail.send(msg)
        print(f"[DEBUG] Email sent to {to} successfully.")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        print(f"--- MOCK EMAIL ---")
        print(f"To: {to}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        if html:
            print(f"HTML: [HTML Content Provided]")
        print(f"------------------")
        return False

def hash_password(password):
    """Hashes a password using Bcrypt."""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(hashed_password, password):
    """Checks a password against its hash."""
    return bcrypt.check_password_hash(hashed_password, password)

def generate_voting_token(user_id, election_id):
    """Generates a secure HMAC-SHA256 based voting token."""
    secret_key = os.getenv('HMAC_KEY', 'default_hmac_secret').encode()
    message = f"{user_id}-{election_id}-{random.random()}".encode()
    token = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return token

def hash_token(token):
    """Hashes a raw token with SHA-256 for database storage."""
    return hashlib.sha256(token.encode()).hexdigest()

def log_event(user_id, action, description, anomaly=0.0):
    """Logs a system event to the database."""
    from db import get_db_connection
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_logs (user_id, action, description, anomaly) 
            VALUES (%s, %s, %s, %s)
        """, (user_id, action, description, anomaly))
        conn.commit()
    except Exception as e:
        print(f"[ERROR] Logging event: {e}")
    finally:
        cursor.close()
        conn.close()
