from flask import Blueprint, render_template, jsonify, session
from db import get_db_connection
from decorators import login_required

results_bp = Blueprint('results', __name__, url_prefix='/results')

@results_bp.route('/')
@login_required
def all_results():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    role = session.get('role')
    status_filter = "('active', 'closed')" if role == 'admin' else "('closed')"
    
    cursor.execute(f"""
        SELECT e.*, 
               (SELECT COUNT(*) FROM votes WHERE election_id = e.id) as total_votes
        FROM elections e
        WHERE status IN {status_filter}
        ORDER BY created_at DESC
    """)
    elections_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('results.html', elections=elections_list)

@results_bp.route('/<int:eid>')
@login_required
def view_election(eid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM elections WHERE id = %s", (eid,))
    election = cursor.fetchone()
    
    if not election or election['status'] not in ['active', 'closed']:
        return "Election results not available.", 404
        
    if election['status'] == 'active' and session.get('role') != 'admin':
        return "Results are hidden until the election officially closes.", 403
        
    cursor.execute("""
        SELECT c.*, 
               COUNT(v.id) as vote_count
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        WHERE c.election_id = %s
        GROUP BY c.id
    """, (eid,))
    candidates_list = cursor.fetchall()
    
    total_votes = sum(c['vote_count'] for c in candidates_list)
    
    # Calculate percentages and identify winner if closed
    winner = None
    if election['status'] == 'closed' and candidates_list:
        winner = max(candidates_list, key=lambda x: x['vote_count'])
        if winner['vote_count'] == 0: winner = None

    for c in candidates_list:
        c['percentage'] = (c['vote_count'] / total_votes * 100) if total_votes > 0 else 0
        
    cursor.close()
    conn.close()
    return render_template('election_results.html', election=election, candidates=candidates_list, total_votes=total_votes, winner=winner)

@results_bp.route('/api/<int:eid>')
@login_required
def results_api(eid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT status FROM elections WHERE id = %s", (eid,))
    election = cursor.fetchone()
    if not election or (election['status'] == 'active' and session.get('role') != 'admin'):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Unauthorized'}), 403
        
    cursor.execute("""
        SELECT c.id, c.name, COUNT(v.id) as vote_count
        FROM candidates c
        LEFT JOIN votes v ON v.candidate_id = c.id
        WHERE c.election_id = %s
        GROUP BY c.id
    """, (eid,))
    candidates_list = cursor.fetchall()
    
    total_votes = sum(c['vote_count'] for c in candidates_list)
    for c in candidates_list:
        c['percentage'] = (c['vote_count'] / total_votes * 100) if total_votes > 0 else 0
        
    cursor.close()
    conn.close()
    return jsonify({
        'election_id': eid,
        'total_votes': total_votes,
        'candidates': candidates_list
    })
