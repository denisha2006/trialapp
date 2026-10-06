import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from datetime import datetime
from flask import session, url_for
from routes.admin import allowed_file

class TestAdminRoutesWhiteBox:
    """White-box structural & path test suite for routes/admin.py."""

    # --- allowed_file Helper Tests ---
    @pytest.mark.parametrize("filename, expected", [
        ("photo.png", True),
        ("photo.JPEG", True),
        ("vector.svg", True),
        ("document.pdf", False),
        ("script.py", False),
        ("no_extension", False)
    ])
    def test_allowed_file(self, filename, expected):
        """Branch Coverage: File extension whitelist validator."""
        assert allowed_file(filename) is expected

    # --- Dashboard & Authorization Tests ---
    def test_admin_dashboard_unauthorized_voter(self, app, client):
        """Path 1: Voter accessing admin dashboard redirected to voter dashboard."""
        with client.session_transaction() as sess:
            sess['user_id'] = 5
            sess['role'] = 'voter'

        response = client.get('/admin/dashboard')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.dashboard'))

    def test_admin_dashboard_success(self, client, mock_db):
        """Path 2: Authorized admin accessing dashboard."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        fetch_responses = [{'count': 50}, {'count': 120}, {'count': 2}, {'count': 45}]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else {'count': 0}
        mock_db.cursor_obj.set_fetchall([])

        response = client.get('/admin/dashboard')
        assert response.status_code == 200

    # --- Elections Management Tests ---
    def test_admin_elections_list(self, client, mock_db):
        """Statement Coverage: Listing all elections."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'title': 'National Election', 'status': 'active'}
        ])

        response = client.get('/admin/elections')
        assert response.status_code == 200

    def test_admin_create_election_post(self, app, client, mock_db):
        """Statement & Path Coverage: Creating new election with 12h to 24h conversion."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        with patch('routes.admin.log_event'):
            response = client.post('/admin/elections/create', data={
                'title': 'Board Election',
                'description': 'Select new board members',
                'start_date': '2026-10-10',
                'start_time': '09:30',
                'start_period': 'AM',
                'end_date': '2026-10-12',
                'end_time': '05:00',
                'end_period': 'PM'
            })
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.elections'))
            assert mock_db.is_committed is True

    # --- Candidate Management Tests ---
    def test_admin_add_candidate_with_file_upload(self, app, client, mock_db):
        """Branch A: Adding candidate with image file upload."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        data = {
            'name': 'Alice Smith',
            'party': 'Progressive Party',
            'manifesto': 'Education reform',
            'image_file': (BytesIO(b"fake image data"), "alice.png")
        }

        with patch('os.makedirs'), patch('werkzeug.datastructures.FileStorage.save'):
            response = client.post('/admin/elections/1/candidates', data=data, content_type='multipart/form-data')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.candidates', eid=1))
            assert mock_db.is_committed is True

    def test_admin_delete_candidate_success(self, app, client, mock_db):
        """Branch 1: Deleting existing candidate."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchone({'id': 5, 'name': 'Bob candidate'})

        with patch('routes.admin.log_event'):
            response = client.post('/admin/elections/1/candidates/5/delete')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.candidates', eid=1))
            assert mock_db.is_committed is True

    def test_admin_delete_candidate_not_found(self, client, mock_db):
        """Branch 2: Deleting non-existent candidate."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchone(None)

        response = client.post('/admin/elections/1/candidates/999/delete')
        assert response.status_code == 302

    # --- Election Phase Transition Tests ---
    def test_update_status_pre_vote_to_active(self, app, client, mock_db):
        """Branch 1: Phase transition pre_vote -> active generates and sends voting tokens."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        fetch_responses = [{'status': 'pre_vote'}, None]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None
        mock_db.cursor_obj.set_fetchall([
            {'user_id': 10, 'email': 'voter10@example.com', 'full_name': 'Voter Ten', 'title': 'City Election'}
        ])

        with patch('routes.admin.send_email', return_value=True), \
             patch('routes.admin.log_event'):
            response = client.post('/admin/elections/1/status', data={'status': 'active'})
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.elections'))
            assert mock_db.is_committed is True

    def test_update_status_active_to_closed(self, app, client, mock_db):
        """Branch 2: Phase transition active -> closed emails results declared notifications."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchone({'status': 'active', 'title': 'City Election'})
        mock_db.cursor_obj.set_fetchall([
            {'email': 'voter10@example.com', 'full_name': 'Voter Ten'}
        ])

        with patch('routes.admin.send_email', return_value=True), \
             patch('routes.admin.log_event'):
            response = client.post('/admin/elections/1/status', data={'status': 'closed'})
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.elections'))

    # --- Approvals & Token Resend Tests ---
    def test_admin_resend_token_success(self, app, client, mock_db):
        """Branch 1: Admin resending token for approved voter in active election."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        fetch_responses = [
            {'user_id': 10, 'election_id': 1, 'email': 'voter@example.com', 'full_name': 'Voter Ten', 'title': 'Election Title', 'election_status': 'active'},
            {'id': 77}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        with patch('routes.admin.send_email', return_value=True), \
             patch('routes.admin.log_event'):
            response = client.get('/admin/approvals/100/resend')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('admin.approvals'))

    # --- Voters & Live Monitor Tests ---
    def test_admin_voters_list(self, client, mock_db):
        """Statement Coverage: Listing voters."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchall([])
        response = client.get('/admin/voters')
        assert response.status_code == 200

    def test_admin_live_monitor(self, client, mock_db):
        """Statement Coverage: Admin live security monitor page."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        fetch_responses = [
            {'active_count': 12},
            {'flagged_count': 1},
            {'id': 1, 'title': 'Current Election'}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else {'active_count': 0, 'flagged_count': 0, 'id': 1, 'title': 'Fallback'}
        
        fetchall_responses = [
            [{'user_id': 1, 'action': 'LOGIN', 'anomaly': 0.0, 'email': 'admin@example.com', 'timestamp': datetime.now(), 'description': 'Login', 'ip_address': '127.0.0.1'}],
            [{'name': 'Candidate A', 'vote_count': 10}]
        ]
        mock_db.cursor_obj.fetchall = lambda: fetchall_responses.pop(0) if fetchall_responses else []

        response = client.get('/admin/live-monitor')
        assert response.status_code == 200
