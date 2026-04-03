from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from utils import hash_token, log_event
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
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO election_participants (election_id, user_id, status) VALUES (%s, %s, 'pending')", (eid, uid))
        conn.commit()
        log_event(uid, 'JOIN_REQUEST', f"Requested access to election ID: {eid}")
        flash("Request to join sent! Waiting for admin approval.", "info")
    except Exception as e:
        flash("You have already requested to join this election.", "warning")
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
        return redirect(url_for('results.view_election', eid=eid))
        
    if request.method == 'POST':
        token = request.form['token']
        candidate_id = request.form['candidate_id']
        hashed_token = hash_token(token)
        
        # Verify Token
        cursor.execute("SELECT * FROM voting_tokens WHERE election_id = %s AND user_id = %s AND token_hash = %s AND is_used = 0", 
                       (eid, uid, hashed_token))
        token_record = cursor.fetchone()
        
        if token_record:
            # Cast Vote
            cursor.execute("INSERT INTO votes (election_id, user_id, candidate_id) VALUES (%s, %s, %s)", (eid, uid, candidate_id))
            cursor.execute("UPDATE voting_tokens SET is_used = 1 WHERE id = %s", (token_record['id'],))
            conn.commit()
            log_event(uid, 'VOTE_CAST', f"Voted in election ID: {eid}")
            flash("Vote cast successfully!", "success")
            return redirect(url_for('results.view_election', eid=eid))
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
