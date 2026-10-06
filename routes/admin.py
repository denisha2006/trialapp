from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from db import get_db_connection
from utils import generate_voting_token, hash_token, send_email, log_event, clean_image_url
from decorators import login_required, admin_required
import os
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'candidates')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Stats
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'voter'")
    total_voters = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM votes")
    total_votes = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM elections WHERE status = 'active'")
    active_elections_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM election_participants WHERE status = 'approved'")
    approved_participants = cursor.fetchone()['count']
    
    # Recent Elections
    cursor.execute("SELECT * FROM elections ORDER BY created_at DESC LIMIT 5")
    recent_elections = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/dashboard.html', 
                           total_voters=total_voters, 
                           total_votes=total_votes, 
                           active_elections_count=active_elections_count, 
                           approved_participants=approved_participants,
                           recent_elections=recent_elections)

@admin_bp.route('/elections')
@login_required
@admin_required
def elections():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM elections ORDER BY created_at DESC")
    all_elections = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/elections.html', elections=all_elections)

@admin_bp.route('/elections/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_election():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_date_val = request.form['start_date']
        start_time_raw = request.form['start_time']
        start_period = request.form.get('start_period', 'AM')
        
        end_date_val = request.form['end_date']
        end_time_raw = request.form['end_time']
        end_period = request.form.get('end_period', 'AM')

        def convert_to_24h(time_str, period):
            if not time_str: return "00:00"
            try:
                # Most browsers send type="time" as 24h string "HH:MM"
                # If the user used our AM/PM dropdown, we should adjust if it's 12h format
                h, m = map(int, time_str.split(':'))
                if period == 'PM' and h < 12: h += 12
                elif period == 'AM' and h == 12: h = 0
                return f"{h:02d}:{m:02d}"
            except: return time_str

        start_time_24 = convert_to_24h(start_time_raw, start_period)
        end_time_24 = convert_to_24h(end_time_raw, end_period)
        
        full_start_date = f"{start_date_val} {start_time_24}"
        full_end_date = f"{end_date_val} {end_time_24}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO elections (title, description, start_date, end_date) VALUES (%s, %s, %s, %s)", 
                       (title, description, full_start_date, full_end_date))
        conn.commit()
        
        # Log election creation
        log_event(session.get('user_id'), 'ELECTION_CREATED', f"New election created: {title}")
        cursor.close()
        conn.close()
        flash("Election created successfully.", "success")
        return redirect(url_for('admin.elections'))
        
    return render_template('admin/create_election.html')

@admin_bp.route('/elections/<int:eid>/candidates', methods=['GET', 'POST'])
@login_required
@admin_required
def candidates(eid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        party = request.form['party']
        manifesto = request.form['manifesto']
        image_url = request.form.get('image_url', '').strip()
        
        file = request.files.get('image_file')
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f"{eid}_{int(datetime.now().timestamp())}.{ext}")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            image_url = f"/static/uploads/candidates/{filename}"
        elif image_url:
            image_url = clean_image_url(image_url)
        
        cursor.execute("INSERT INTO candidates (election_id, name, party_affiliation, manifesto, image_url) VALUES (%s, %s, %s, %s, %s)", 
                       (eid, name, party, manifesto, image_url))
        conn.commit()
        flash("Candidate added successfully.", "success")
        return redirect(url_for('admin.candidates', eid=eid))
    
    cursor.execute("SELECT * FROM elections WHERE id = %s", (eid,))
    election = cursor.fetchone()
    cursor.execute("SELECT * FROM candidates WHERE election_id = %s", (eid,))
    cands = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin/candidates.html', election=election, candidates=cands)

@admin_bp.route('/elections/<int:eid>/candidates/<int:cid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_candidate(eid, cid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM candidates WHERE id = %s AND election_id = %s", (cid, eid))
    candidate = cursor.fetchone()
    
    if candidate:
        cursor.execute("DELETE FROM candidates WHERE id = %s AND election_id = %s", (cid, eid))
        conn.commit()
        log_event(session.get('user_id'), 'CANDIDATE_DELETED', f"Candidate '{candidate['name']}' (ID {cid}) deleted from election ID {eid}")
        flash(f"Candidate '{candidate['name']}' removed successfully.", "success")
    else:
        flash("Candidate not found.", "danger")
        
    cursor.close()
    conn.close()
    return redirect(url_for('admin.candidates', eid=eid))

@admin_bp.route('/elections/<int:eid>/candidates/<int:cid>/edit', methods=['POST'])
@login_required
@admin_required
def edit_candidate(eid, cid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM candidates WHERE id = %s AND election_id = %s", (cid, eid))
    candidate = cursor.fetchone()
    
    if not candidate:
        flash("Candidate not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('admin.candidates', eid=eid))
        
    name = request.form['name']
    party = request.form['party']
    manifesto = request.form['manifesto']
    image_url = request.form.get('image_url', '').strip()
    
    file = request.files.get('image_file')
    if file and file.filename != '' and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{eid}_{cid}_{int(datetime.now().timestamp())}.{ext}")
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        final_image_url = f"/static/uploads/candidates/{filename}"
    elif image_url:
        final_image_url = clean_image_url(image_url)
    else:
        final_image_url = candidate['image_url']
        
    cursor.execute("""
        UPDATE candidates 
        SET name = %s, party_affiliation = %s, manifesto = %s, image_url = %s 
        WHERE id = %s AND election_id = %s
    """, (name, party, manifesto, final_image_url, cid, eid))
    conn.commit()
    
    log_event(session.get('user_id'), 'CANDIDATE_EDITED', f"Candidate '{name}' (ID {cid}) updated in election ID {eid}")
    flash(f"Candidate '{name}' updated successfully.", "success")
    
    cursor.close()
    conn.close()
    return redirect(url_for('admin.candidates', eid=eid))



@admin_bp.route('/elections/<int:eid>/status', methods=['POST'])
@login_required
@admin_required
def update_status(eid):
    new_status = request.form['status']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Logic for Phase Transition from Pre-vote to Active
    if new_status == 'active':
        # Retrieve previous status
        cursor.execute("SELECT status FROM elections WHERE id = %s", (eid,))
        old_status = cursor.fetchone()['status']
        
        if old_status == 'pre_vote':
            # Generate tokens for all approved participants
            cursor.execute("""
                SELECT ep.user_id, u.email, u.full_name, e.title 
                FROM election_participants ep
                JOIN users u ON ep.user_id = u.id
                JOIN elections e ON ep.election_id = e.id
                WHERE ep.election_id = %s AND ep.status = 'approved'
            """, (eid,))
            participants = cursor.fetchall()
            
            for p in participants:
                raw_token = generate_voting_token(p['user_id'], eid)
                hashed = hash_token(raw_token)
                
                # Check if token already exists to prevent duplicates
                cursor.execute("SELECT id FROM voting_tokens WHERE election_id = %s AND user_id = %s", (eid, p['user_id']))
                if not cursor.fetchone():
                    expires_at = datetime.now() + timedelta(minutes=15)
                    cursor.execute("INSERT INTO voting_tokens (election_id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)", 
                                   (eid, p['user_id'], hashed, expires_at))
                    
                    # Send token via email
                    subject = f"Your Voting Token for {p['title']}"
                    body = f"Hello {p['full_name']},\n\nYour secret voting token is: {raw_token}\n\nKeep this token safe. It is required to cast your vote."
                    send_email(p['email'], subject, body)
            
            conn.commit()
            log_event(session.get('user_id'), 'ELECTION_ACTIVATED', f"Election ID {eid} moved to ACTIVE phase")
            flash("Election activated! Tokens have been sent to approved voters.", "success")
            
    elif new_status == 'closed':
        # Retrieve previous status and title
        cursor.execute("SELECT status, title FROM elections WHERE id = %s", (eid,))
        row = cursor.fetchone()
        
        if row and row['status'] == 'active':
            # Send notification to voters
            cursor.execute("""
                SELECT u.email, u.full_name 
                FROM election_participants ep
                JOIN users u ON ep.user_id = u.id
                WHERE ep.election_id = %s
            """, (eid,))
            participants = cursor.fetchall()
            
            for p in participants:
                subject = f"Results Declared: {row['title']}"
                body = f"Hello {p['full_name']},\n\nThe results for '{row['title']}' have been finalized and declared! You can now log in to the AuthVote platform and check the outcome.\n\nThank you for participating."
                html = f"""
                <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 40px; border-radius: 12px; text-align: center;">
                    <h2 style="color: #3b82f6; margin-bottom: 20px;">Results Declared!</h2>
                    <p style="font-size: 1.1rem; margin-bottom: 30px;">Hello {p['full_name']}, the results for <strong>{row['title']}</strong> have just been finalized and the polls are officially closed.</p>
                    <div style="margin: 30px 0;">
                        <span style="background-color: rgba(59, 130, 246, 0.1); color: #3b82f6; padding: 12px 24px; border: 1px solid #3b82f6; border-radius: 6px; font-weight: 600;">Log in to view the official results</span>
                    </div>
                    <hr style="border: 0; border-top: 1px solid #334155; margin: 30px 0;">
                    <p style="font-size: 0.8rem; color: #64748b;">© 2026 AuthVote - Secure Polling Platform</p>
                </div>
                """
                send_email(p['email'], subject, body, html=html)
            
            log_event(session.get('user_id'), 'ELECTION_CLOSED_NOTIFIED', f"Election ID {eid} closed and notifications sent.")
            flash("Election closed! Notification emails have been sent to all registered participants.", "success")

    cursor.execute("UPDATE elections SET status = %s WHERE id = %s", (new_status, eid))
    conn.commit()
    log_event(session.get('user_id'), 'ELECTION_STATUS_CHANGE', f"Election ID {eid} status changed to {new_status}")
    cursor.close()
    conn.close()
    return redirect(url_for('admin.elections'))

@admin_bp.route('/approvals')
@login_required
@admin_required
def approvals():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ep.id, u.full_name, u.email, e.title as election_title, ep.status, ep.requested_at
        FROM election_participants ep
        JOIN users u ON ep.user_id = u.id
        JOIN elections e ON ep.election_id = e.id
        ORDER BY ep.requested_at DESC
    """)
    reqs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/approvals.html', requests=reqs)

@admin_bp.route('/approvals/<int:rid>/resend')
@login_required
@admin_required
def resend_token(rid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get request details
    cursor.execute("""
        SELECT ep.user_id, ep.election_id, u.email, u.full_name, e.title, e.status as election_status
        FROM election_participants ep
        JOIN users u ON ep.user_id = u.id
        JOIN elections e ON ep.election_id = e.id
        WHERE ep.id = %s AND ep.status = 'approved'
    """, (rid,))
    req_data = cursor.fetchone()
    
    if req_data and req_data['election_status'] == 'active':
        raw_token = generate_voting_token(req_data['user_id'], req_data['election_id'])
        hashed = hash_token(raw_token)
        
        # Check if token exists - update if it does, insert if not
        cursor.execute("SELECT id FROM voting_tokens WHERE election_id = %s AND user_id = %s", 
                       (req_data['election_id'], req_data['user_id']))
        token_record = cursor.fetchone()
        
        if token_record:
            expires_at = datetime.now() + timedelta(minutes=15)
            cursor.execute("UPDATE voting_tokens SET token_hash = %s, is_used = 0, expires_at = %s WHERE id = %s", 
                           (hashed, expires_at, token_record['id']))
        else:
            expires_at = datetime.now() + timedelta(minutes=15)
            cursor.execute("INSERT INTO voting_tokens (election_id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)", 
                           (req_data['election_id'], req_data['user_id'], hashed, expires_at))
        
        # Send token with premium HTML template
        subject = f"IMPORTANT: Your New Voting Token for {req_data['title']}"
        body = f"Hello {req_data['full_name']},\n\nYour secret voting token is: {raw_token}\n\nKeep this token safe. It is required to cast your vote."
        html = f"""
        <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: white; padding: 40px; border-radius: 12px; text-align: center;">
            <h2 style="color: #3b82f6; margin-bottom: 20px;">AuthVote New Token</h2>
            <p style="font-size: 1.1rem; margin-bottom: 30px;">Hello {req_data['full_name']}, here is your requested voting token for <strong>{req_data['title']}</strong>.</p>
            <div style="background-color: #1e293b; padding: 20px; border: 1px solid #334155; border-radius: 8px; margin-bottom: 30px;">
                <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">Your Secret Voting Token</p>
                <code style="font-size: 1.5rem; color: #fff; font-family: monospace; word-break: break-all;">{raw_token}</code>
            </div>
            <p style="font-size: 0.9rem; color: #94a3b8;">This token replaces any previous tokens you may have received. Keep it secret!</p>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 30px 0;">
            <p style="font-size: 0.8rem; color: #64748b;">© 2026 AuthVote - Secure Polling Platform</p>
        </div>
        """
        send_email(req_data['email'], subject, body, html=html)
        conn.commit()
        log_event(session.get('user_id'), 'TOKEN_RESENT', f"New token sent to voter ID {req_data['user_id']} for election {req_data['election_id']}")
        flash("New token generated and sent successfully!", "success")
    else:
        flash("Cannot resend token. Either the voter is not approved yet or the election is not active.", "danger")
        
    cursor.close()
    conn.close()
    return redirect(url_for('admin.approvals'))

@admin_bp.route('/voters')
@login_required
@admin_required
def voters():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.*, (SELECT COUNT(*) FROM election_participants WHERE user_id = u.id) as joined_count
        FROM users u WHERE role = 'voter'
    """)
    vList = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/voters.html', voters=vList)

@admin_bp.route('/live-monitor')
@login_required
@admin_required
def live_monitor():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch real logs
    cursor.execute("""
        SELECT l.*, u.email 
        FROM system_logs l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.timestamp DESC 
        LIMIT 20
    """)
    logs = cursor.fetchall()
    
    # Stats for Mission Control
    cursor.execute("SELECT COUNT(DISTINCT user_id) as active_count FROM system_logs WHERE timestamp > NOW() - INTERVAL 1 HOUR")
    active_sessions = cursor.fetchone()['active_count'] or 0
    
    cursor.execute("SELECT COUNT(*) as flagged_count FROM system_logs WHERE anomaly > 0.6")
    flagged_ips = cursor.fetchone()['flagged_count'] or 0

    # Fetch latest election and its results
    cursor.execute("SELECT id, title FROM elections ORDER BY created_at DESC LIMIT 1")
    latest_election = cursor.fetchone()
    
    results_data = {'labels': [], 'counts': [], 'title': "No Active Election"}
    if latest_election:
        results_data['title'] = latest_election['title']
        cursor.execute("""
            SELECT c.name, COUNT(v.id) as vote_count 
            FROM candidates c 
            LEFT JOIN votes v ON c.id = v.candidate_id 
            WHERE c.election_id = %s 
            GROUP BY c.id
        """, (latest_election['id'],))
        candidates_results = cursor.fetchall()
        for cand in candidates_results:
            results_data['labels'].append(cand['name'])
            results_data['counts'].append(cand['vote_count'])
    
    cursor.close()
    conn.close()
    
    return render_template('admin/live_monitor.html', 
                           logs=logs, 
                           active_sessions=active_sessions, 
                           flagged_ips=flagged_ips,
                           results=results_data)


@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM elections")
    elections_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/settings.html', elections=elections_list)
