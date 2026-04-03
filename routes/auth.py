from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from db import get_db_connection
from utils import generate_otp, send_email, hash_password, check_password, log_event
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        voter_id = request.form['voter_id']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('auth.register'))
        
        hashed = hash_password(password)
        otp = generate_otp()
        expiry = datetime.now() + timedelta(minutes=10)
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for('auth.register'))
        
        cursor = conn.cursor()
        try:
            query = "INSERT INTO users (full_name, voter_id, email, password_hash, role, otp, otp_expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (full_name, voter_id, email, hashed, role, otp, expiry))
            conn.commit()
            
            # Log registration
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            new_uid = cursor.fetchone()[0]
            log_event(new_uid, 'REGISTER', f"New {role} account created for {full_name}")
            
            subject = f"Your OTP for AuthVote Registration"
            body = f"Your OTP for registration is: {otp}"
            html = f"""
            <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 40px; border-radius: 12px; text-align: center;">
                <h2 style="color: #3b82f6; margin-bottom: 20px;">AuthVote Registration</h2>
                <p style="font-size: 1.1rem; margin-bottom: 30px;">Your One-Time Password (OTP) for secure registration is:</p>
                <div style="background-color: #1e293b; padding: 20px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 30px;">
                    <h1 style="font-size: 2.5rem; color: #fff; margin: 0; letter-spacing: 5px;">{otp}</h1>
                </div>
                <p style="font-size: 0.9rem; color: #94a3b8;">This code will expire shortly. Do not share it with anyone.</p>
                <hr style="border: 0; border-top: 1px solid #334155; margin: 30px 0;">
                <p style="font-size: 0.8rem; color: #64748b;">© 2026 AuthVote - Secure Polling Platform</p>
            </div>
            """
            send_email(email, subject, body, html=html)
            session['pending_email'] = email
            return redirect(url_for('auth.verify_otp'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for('auth.register'))
        finally:
            cursor.close()
            conn.close()
            
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        
        if user and check_password(user['password_hash'], password):
            if not user['is_verified']:
                session['pending_email'] = email
                flash("Please verify your account first.", "info")
                return redirect(url_for('auth.verify_otp'))
            
            otp = generate_otp()
            expiry = datetime.now() + timedelta(minutes=10)
            cursor.execute("UPDATE users SET otp = %s, otp_expires_at = %s WHERE id = %s", (otp, expiry, user['id']))
            conn.commit()
            
            # Log login attempt
            log_event(user['id'], 'LOGIN_ATTEMPT', "2FA verification required")
            
            send_email(email, "Single-Use 2FA Code - AuthVote", f"Your 2FA OTP is: {otp}")
            session['pending_email'] = email
            session['login_in_progress'] = True
            return redirect(url_for('auth.verify_otp'))
        else:
            # Log failed attempt with high anomaly
            log_event(None, 'LOGIN_FAILED', f"Failed login attempt for email: {email}", anomaly=0.75)
            flash("Invalid email or password.", "danger")
        
        cursor.close()
        conn.close()
    return render_template('login.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('pending_email')
    if not email:
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        otp = request.form['otp']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and user['otp'] == otp and user['otp_expires_at'] > datetime.now():
            cursor.execute("UPDATE users SET is_verified = 1, otp = NULL WHERE id = %s", (user['id'],))
            conn.commit()
            
            # Log verification success
            log_event(user['id'], 'VERIFY_SUCCESS', "OTP verification successful")
            
            # If 2FA login
            if session.get('login_in_progress'):
                session.clear()
                session['user_id'] = user['id']
                session['full_name'] = user['full_name']
                session['role'] = user['role']
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin.dashboard'))
                return redirect(url_for('voter.dashboard'))
            
            # If registration verification
            flash("Account verified! Please login.", "success")
            session.pop('pending_email', None)
            return redirect(url_for('auth.login'))
        else:
            flash("Invalid or expired OTP.", "danger")
        
        cursor.close()
        conn.close()
    return render_template('verify_otp.html', email=email)

@auth_bp.route('/logout')
def logout():
    uid = session.get('user_id')
    log_event(uid, 'LOGOUT', "User logged out")
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for('auth.login'))
