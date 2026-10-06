from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from db import get_db_connection
from utils import hash_token, log_event, generate_voting_token, send_email
from decorators import login_required

voter_bp = Blueprint('voter', __name__, url_prefix='/voter')

@voter_bp.route('/dashboard')
@login_required
def dashboard():
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Voter stats
    cursor.execute("""
        SELECT COUNT(*) as count FROM elections 
        WHERE status IN ('pre_vote', 'active')
    """)
    available_elections = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM votes WHERE user_id = %s", (uid,))
    my_votes_count = cursor.fetchone()['count']
    
    # Elections with status
    cursor.execute("""
        SELECT e.*, ep.status as participation_status
        FROM elections e
        LEFT JOIN election_participants ep ON e.id = ep.election_id AND ep.user_id = %s
        WHERE e.status IN ('pre_vote', 'active')
        ORDER BY e.created_at DESC
    """, (uid,))
    elections_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('voter/dashboard.html', 
                           available_elections=available_elections, 
                           my_votes_count=my_votes_count,
                           elections=elections_list)

@voter_bp.route('/secure-votes')
@login_required
def secure_votes():
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, ep.status as participation_status
        FROM elections e
        LEFT JOIN election_participants ep ON e.id = ep.election_id AND ep.user_id = %s
        WHERE e.status IN ('pre_vote', 'active')
    """, (uid,))
    elections_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('voter/secure_votes.html', elections=elections_list)

@voter_bp.route('/join/<int:eid>')
@login_required
def join_election(eid):
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Auto-approve the voter immediately
        cursor.execute(
            "INSERT INTO election_participants (election_id, user_id, status) VALUES (%s, %s, 'approved')",
            (eid, uid)
        )
        conn.commit()
        log_event(uid, 'JOIN_APPROVED', f"Auto-approved for election ID: {eid}")

        # If election is already active, generate and send token now
        cursor.execute("SELECT status, title FROM elections WHERE id = %s", (eid,))
        election = cursor.fetchone()

        if election and election['status'] == 'active':
            cursor.execute("SELECT email, full_name FROM users WHERE id = %s", (uid,))
            user = cursor.fetchone()

            # Only create token if one doesn't already exist
            cursor.execute(
                "SELECT id FROM voting_tokens WHERE election_id = %s AND user_id = %s",
                (eid, uid)
            )
            if not cursor.fetchone():
                raw_token = generate_voting_token(uid, eid)
                hashed = hash_token(raw_token)
                expires_at = datetime.now() + timedelta(minutes=15)
                cursor.execute(
                    "INSERT INTO voting_tokens (election_id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)",
                    (eid, uid, hashed, expires_at)
                )
                conn.commit()

                subject = f"Your Voting Token for {election['title']}"
                body = f"Hello {user['full_name']},\n\nYour secret voting token is: {raw_token}\n\nKeep this token safe."
                html = f"""
                <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 40px; border-radius: 12px; text-align: center;">
                    <h2 style="color: #3b82f6; margin-bottom: 20px;">AuthVote Secure Token</h2>
                    <p style="font-size: 1.1rem; margin-bottom: 30px;">Hello {user['full_name']}, you have been approved to vote in <strong>{election['title']}</strong>.</p>
                    <div style="background-color: #1e293b; padding: 20px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 30px;">
                        <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">Your Secret Voting Token</p>
                        <code style="font-size: 1.5rem; color: #fff; font-family: monospace; word-break: break-all;">{raw_token}</code>
                    </div>
                    <p style="font-size: 0.9rem; color: #94a3b8;">Copy this token and paste it into the voting booth on your dashboard. Keep it secret!</p>
                    <hr style="border: 0; border-top: 1px solid #334155; margin: 30px 0;">
                    <p style="font-size: 0.8rem; color: #64748b;">© 2026 AuthVote - Secure Polling Platform</p>
                </div>
                """
                send_email(user['email'], subject, body, html=html)
                flash("You have been approved! Your voting token has been sent to your email.", "success")
            else:
                flash("You are already registered for this election.", "info")
        else:
            flash("You have been approved for this election! You will receive your voting token once the election goes live.", "success")

    except Exception as e:
        conn.rollback()
        flash("You have already joined this election.", "warning")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('voter.secure_votes'))

@voter_bp.route('/vote/<int:eid>', methods=['GET', 'POST'])
@login_required
def vote(eid):
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Validation
    cursor.execute("""
        SELECT e.*, ep.status as participation_status
        FROM elections e
        JOIN election_participants ep ON e.id = ep.election_id
        WHERE e.id = %s AND ep.user_id = %s
    """, (eid, uid))
    election_data = cursor.fetchone()
    
    if not election_data or election_data['status'] != 'active' or election_data['participation_status'] != 'approved':
        flash("You are not eligible to vote in this election at this time.", "danger")
        return redirect(url_for('voter.dashboard'))
    
    # Check if already voted
    cursor.execute("SELECT id FROM votes WHERE election_id = %s AND user_id = %s", (eid, uid))
    if cursor.fetchone():
        flash("You have already cast your vote for this election.", "warning")
        return redirect(url_for('voter.dashboard'))
        
    if request.method == 'POST':
        token = request.form.get('token', '').strip().upper()
        candidate_id = request.form.get('candidate_id')
        hashed_token = hash_token(token)
        
        # Verify Token
        cursor.execute("SELECT * FROM voting_tokens WHERE election_id = %s AND user_id = %s AND token_hash = %s AND is_used = 0", 
                       (eid, uid, hashed_token))
        token_record = cursor.fetchone()
        
        if token_record:
            if token_record['expires_at'] and token_record['expires_at'] < datetime.now():
                flash("Your token has expired. Please resend a new token below.", "danger")
                return redirect(url_for('voter.vote', eid=eid))
                
            # Cast Vote
            cursor.execute("INSERT INTO votes (election_id, user_id, candidate_id) VALUES (%s, %s, %s)", (eid, uid, candidate_id))
            cursor.execute("UPDATE voting_tokens SET is_used = 1 WHERE id = %s", (token_record['id'],))
            conn.commit()
            log_event(uid, 'VOTE_CAST', f"Voted in election ID: {eid}")
            flash("Vote cast successfully! Results will be available when the election closes.", "success")
            return redirect(url_for('voter.dashboard'))
        else:
            log_event(uid, 'INVALID_TOKEN', f"Failed vote attempt (invalid token) in election ID: {eid}", anomaly=0.6)
            flash("Invalid or already used token. Please check your email.", "danger")
            
    # Get Candidates
    cursor.execute("SELECT * FROM candidates WHERE election_id = %s", (eid,))
    cands = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('voter/vote.html', election=election_data, candidates=cands)

@voter_bp.route('/profile')
@login_required
def profile():
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (uid,))
    user = cursor.fetchone()
    
    cursor.execute("""
        SELECT e.title, ep.status as participation_status, e.status as election_status, ep.requested_at
        FROM election_participants ep
        JOIN elections e ON ep.election_id = e.id
        WHERE ep.user_id = %s
        ORDER BY ep.requested_at DESC
    """, (uid,))
    history = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('voter/profile.html', user=user, participation_history=history)

@voter_bp.route('/resend-token/<int:eid>', methods=['POST'])
@login_required
def resend_token(eid):
    uid = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT e.title, ep.status as participation_status, u.email, u.full_name
            FROM elections e
            JOIN election_participants ep ON e.id = ep.election_id
            JOIN users u ON ep.user_id = u.id
            WHERE e.id = %s AND ep.user_id = %s AND e.status = 'active'
        """, (eid, uid))
        data = cursor.fetchone()
        
        if data and data['participation_status'] == 'approved':
            raw_token = generate_voting_token(uid, eid)
            hashed = hash_token(raw_token)
            expires_at = datetime.now() + timedelta(minutes=15)
            
            cursor.execute("SELECT id FROM voting_tokens WHERE election_id = %s AND user_id = %s", (eid, uid))
            token_record = cursor.fetchone()
            
            if token_record:
                cursor.execute("UPDATE voting_tokens SET token_hash = %s, is_used = 0, expires_at = %s WHERE id = %s", 
                               (hashed, expires_at, token_record['id']))
            else:
                cursor.execute("INSERT INTO voting_tokens (election_id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)", 
                               (eid, uid, hashed, expires_at))
            
            subject = f"Your New Voting Token for {data['title']}"
            body = f"Your new token is {raw_token}"
            html = f"""
            <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 40px; border-radius: 12px; text-align: center;">
                <h2 style="color: #3b82f6; margin-bottom: 20px;">AuthVote New Token</h2>
                <p style="font-size: 1.1rem; margin-bottom: 30px;">Hello {data['full_name']}, here is your requested voting token for <strong>{data['title']}</strong>.</p>
                <div style="background-color: #1e293b; padding: 20px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 30px;">
                    <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">Your Secret Voting Token</p>
                    <code style="font-size: 1.5rem; color: #fff; font-family: monospace; word-break: break-all;">{raw_token}</code>
                </div>
                <p style="font-size: 0.9rem; color: #94a3b8;">This token replaces your old one and expires in 15 minutes.</p>
            </div>
            """
            send_email(data['email'], subject, body, html=html)
            conn.commit()
            log_event(uid, 'TOKEN_AUTORESEND', f"Token actively resent by voter for election {eid}")
            flash("A fresh token has been sent to your email. You have 15 minutes to use it.", "success")
        else:
            flash("Cannot resend token. You are not approved or the election is not active.", "danger")
    except Exception as e:
        conn.rollback()
        flash("An error occurred generating your token.", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('voter.vote', eid=eid))

