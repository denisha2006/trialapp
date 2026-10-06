from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from db import get_db_connection
from utils import generate_otp, send_email, hash_password, check_password, log_event
import random
import string
import uuid

auth_bp = Blueprint('auth', __name__)

def log_mfa_attempt(cursor, user_id, step, success, ip_address):
    status = 'success' if success else 'failed'
    cursor.execute(
        "INSERT INTO mfa_audit_logs (user_id, step_name, status, ip_address) VALUES (%s, %s, %s, %s)",
        (user_id, step, status, ip_address)
    )

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'voter')
        id_number = request.form.get('id_number', '').strip().upper()
        
        if not full_name or not email or not password or not id_number:
            flash("All fields including ID Number are required.", "danger")
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('auth.register'))
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for('auth.register'))
        
        cursor = conn.cursor(dictionary=True)
        try:
            # 1. Check existing email in users
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("An account with this email address already exists.", "warning")
                return redirect(url_for('auth.register'))

            # 2. Generate Registration OTP & store pending data in session
            otp = generate_otp()
            expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
            hashed = hash_password(password)

            session['pending_registration'] = {
                'full_name': full_name,
                'email': email,
                'password_hash': hashed,
                'role': role,
                'id_number': id_number,
                'otp': otp,
                'otp_expires_at': expiry
            }
            
            subject = "Account Registration & ID Verification OTP - AuthVote"
            body = f"Hello {full_name},\n\nYour OTP for registration and ID association (ID: {id_number}) is: {otp}\n\nDo not share this code."
            html = f"""
            <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 30px; border-radius: 12px; text-align: center;">
                <h2 style="color: #38bdf8; margin-bottom: 15px;">Account Registration</h2>
                <p style="font-size: 1rem; margin-bottom: 10px; color: #cbd5e1;">Associating ID Number: <code style="color: #38bdf8;">{id_number}</code> with email <strong>{email}</strong></p>
                <p style="font-size: 0.9rem; margin-bottom: 20px; color: #94a3b8;">Your Registration One-Time Password (OTP) is:</p>
                <div style="background-color: #1e293b; padding: 15px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 20px;">
                    <h1 style="font-size: 2.2rem; color: #fff; margin: 0; letter-spacing: 6px;">{otp}</h1>
                </div>
                <p style="font-size: 0.85rem; color: #94a3b8;">This code will expire in 10 minutes.</p>
            </div>
            """
            send_email(email, subject, body, html=html)
            cursor.close()
            conn.close()
            return redirect(url_for('auth.verify_otp'))

        except Exception as e:
            flash(f"Registration error: {e}", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('auth.register'))
            
    return render_template('register.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    pending = session.get('pending_registration')
    if not pending:
        flash("No pending registration session found. Please register first.", "warning")
        return redirect(url_for('auth.register'))
        
    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        expiry_dt = datetime.fromisoformat(pending['otp_expires_at'])
        
        if pending.get('otp') == otp_input and expiry_dt > datetime.now():
            conn = get_db_connection()
            if not conn:
                flash("Database connection error.", "danger")
                return redirect(url_for('auth.verify_otp'))
                
            cursor = conn.cursor(dictionary=True)
            try:
                query = "INSERT INTO users (full_name, email, password_hash, role, is_verified, id_number) VALUES (%s, %s, %s, %s, 1, %s)"
                cursor.execute(query, (pending['full_name'], pending['email'], pending['password_hash'], pending['role'], pending['id_number']))
                conn.commit()
                
                cursor.execute("SELECT id FROM users WHERE email = %s", (pending['email'],))
                new_uid = cursor.fetchone()['id']
                log_event(new_uid, 'REGISTER_VERIFIED', f"Account registered & ID associated: {pending['id_number']}")
                
                flash("Account registered and ID associated successfully! Please log in.", "success")
                session.pop('pending_registration', None)
                return redirect(url_for('auth.login'))
            except Exception as e:
                flash(f"Error creating account: {e}", "danger")
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Invalid or expired OTP code.", "danger")
        
    return render_template('verify_otp.html', email=pending['email'], id_number=pending['id_number'])

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        id_number = request.form.get('id_number', '').strip().upper()
        
        if not email or not password or not id_number:
            flash("Email, password, and ID Number are required.", "danger")
            return redirect(url_for('auth.login'))

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for('auth.login'))

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password(user['password_hash'], password):
            if not user['is_verified']:
                flash("Your account registration is incomplete. Please complete registration.", "warning")
                cursor.close()
                conn.close()
                return redirect(url_for('auth.register'))
            
            # Verify ID Match against user's registered ID record
            registered_id = user.get('id_number')

            if registered_id:
                if registered_id.strip().upper() != id_number:
                    log_event(user['id'], 'LOGIN_ID_MISMATCH', f"Failed login: ID mismatch ({id_number})", anomaly=0.8)
                    flash("ID Verification Failed: Provided ID Number does not match your registered user record.", "danger")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('auth.login'))
            else:
                # Auto-bind first time for legacy users
                cursor.execute("UPDATE users SET id_number = %s WHERE id = %s", (id_number, user['id']))
                conn.commit()

            log_event(user['id'], 'LOGIN_ATTEMPT', "MFA identity verification required")
            
            session.clear()
            session['pending_mfa_user_id'] = user['id']
            session['pending_email'] = email
            session['pending_id_number'] = id_number
            
            cursor.close()
            conn.close()
            return redirect(url_for('auth.mfa_view'))
        else:
            log_event(None, 'LOGIN_FAILED', f"Failed login attempt for email: {email}", anomaly=0.75)
            flash("Invalid credentials or ID Number.", "danger")
        
        cursor.close()
        conn.close()
    return render_template('login.html')

@auth_bp.route('/mfa')
def mfa_view():
    pending_user_id = session.get('pending_mfa_user_id')
    if not pending_user_id:
        flash("Please log in to initiate multi-factor authentication.", "warning")
        return redirect(url_for('auth.login'))
    return render_template('mfa.html', id_number=session.get('pending_id_number', ''))

@auth_bp.route('/api/v1/auth/mfa/captcha', methods=['GET'])
def get_captcha():
    captcha_chars = "".join(random.choices(string.ascii_uppercase + "23456789", k=6))
    session['captcha_code'] = captcha_chars
    return jsonify({'captcha': captcha_chars})

@auth_bp.route('/api/v1/auth/mfa/verify-panel1', methods=['POST'])
def verify_panel1():
    data = request.json or {}
    user_id = session.get('pending_mfa_user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'No pending MFA session found. Please log in again.'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection error'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'error': 'User record not found'}), 404

        # 1. Validate Captcha
        captcha_input = data.get('captcha', '').strip().upper()
        session_captcha = session.get('captcha_code', '').strip().upper()
        if not session_captcha or captcha_input != session_captcha:
            log_mfa_attempt(cursor, user_id, 'panel1_captcha', False, request.remote_addr)
            conn.commit()
            return jsonify({'success': False, 'error': 'Invalid Captcha code. Please try again.'}), 400

        # 2. Re-verify ID Number
        epic_id = data.get('epic_id', '').strip().upper()
        registered_id = (user.get('id_number') or '').strip().upper()
        
        if registered_id and epic_id and registered_id != epic_id:
            log_mfa_attempt(cursor, user_id, 'panel1_identity', False, request.remote_addr)
            conn.commit()
            return jsonify({'success': False, 'error': 'ID Verification failed: Provided ID Number does not match records.'}), 400

        # 3. Generate Login Identity OTP & send email
        otp = generate_otp()
        expiry = datetime.now() + timedelta(minutes=10)
        cursor.execute("UPDATE users SET otp = %s, otp_expires_at = %s WHERE id = %s", (otp, expiry, user_id))
        
        subject = "ID Verification OTP - AuthVote"
        body = f"Hello {user['full_name']},\n\nYour Login Identity Verification OTP for ID ({user.get('id_number')}) is: {otp}\n\nDo not share this code."
        html = f"""
        <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 30px; border-radius: 12px; text-align: center;">
            <h2 style="color: #38bdf8; margin-bottom: 15px;">Identity Verification</h2>
            <p style="font-size: 1rem; margin-bottom: 10px; color: #cbd5e1;">Your Login Identity Verification OTP is:</p>
            <div style="background-color: #1e293b; padding: 15px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 20px;">
                <h1 style="font-size: 2.2rem; color: #fff; margin: 0; letter-spacing: 6px;">{otp}</h1>
            </div>
            <p style="font-size: 0.85rem; color: #94a3b8;">This code will expire in 10 minutes.</p>
        </div>
        """
        send_email(user['email'], subject, body, html=html)
        log_mfa_attempt(cursor, user_id, 'panel1_complete_otp_sent', True, request.remote_addr)
        
        conn.commit()
        return jsonify({'success': True, 'message': 'ID verified! Login OTP sent to your email.'})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': f"Verification error: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

@auth_bp.route('/api/v1/auth/mfa/verify-otp', methods=['POST'])
def verify_otp_endpoint():
    data = request.json or {}
    user_id = session.get('pending_mfa_user_id')
    otp_input = data.get('otp', '').strip()
    
    if not user_id:
        return jsonify({'success': False, 'error': 'No pending MFA session found'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection error'}), 500
        
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'User record not found'}), 404

        if user.get('otp') and user['otp'] == otp_input and user.get('otp_expires_at') and user['otp_expires_at'] > datetime.now():
            log_mfa_attempt(cursor, user_id, 'panel2_otp', True, request.remote_addr)
            conn.commit()
            return jsonify({'success': True, 'message': 'OTP verification successful.'})
        else:
            log_mfa_attempt(cursor, user_id, 'panel2_otp', False, request.remote_addr)
            conn.commit()
            return jsonify({'success': False, 'error': 'Invalid or expired OTP code.'}), 400

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@auth_bp.route('/api/v1/auth/token/generate', methods=['POST'])
def generate_token():
    user_id = session.get('pending_mfa_user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Unauthorized pending session'}), 401
        
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection error'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user:
            token = str(uuid.uuid4())
            
            cursor.execute("UPDATE users SET otp = NULL WHERE id = %s", (user_id,))
            conn.commit()
            
            # Promote session to full logged-in state
            session.pop('pending_mfa_user_id', None)
            session.pop('pending_email', None)
            session.pop('pending_id_number', None)
            session.pop('captcha_code', None)
            
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            
            log_event(user['id'], 'LOGIN_SUCCESS', f"Unified MFA & ID ({user.get('id_number')}) authentication completed")
            
            redirect_url = url_for('admin.dashboard') if user['role'] == 'admin' else url_for('voter.dashboard')
            
            return jsonify({
                'success': True,
                'token': token,
                'redirect': redirect_url,
                'message': 'MFA completed successfully.'
            })
        else:
            return jsonify({'success': False, 'error': 'User record not found'}), 404
    finally:
        cursor.close()
        conn.close()

@auth_bp.route('/logout')
def logout():
    uid = session.get('user_id') or session.get('pending_mfa_user_id')
    if uid:
        log_event(uid, 'LOGOUT', "User logged out")
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for('auth.login'))
