import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from flask import session, url_for
from utils import hash_token

class TestVoterRoutesWhiteBox:
    """White-box structural & path test suite for routes/voter.py."""

    # --- Dashboard Route Tests ---
    def test_voter_dashboard_unauthorized(self, app, client):
        """Path 1: Unauthenticated access redirected to login."""
        response = client.get('/voter/dashboard')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.login'))

    def test_voter_dashboard_authenticated(self, client, mock_db):
        """Path 2: Authenticated voter dashboard data rendering."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        fetch_responses = [{'count': 2}, {'count': 1}]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else {'count': 0}
        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'title': 'Presidential Election', 'description': 'Main presidential election', 'status': 'active', 'participation_status': 'approved'}
        ])

        response = client.get('/voter/dashboard')
        assert response.status_code == 200

    # --- Secure Votes Route Tests ---
    def test_secure_votes_list(self, client, mock_db):
        """Statement Coverage: Voter secure votes list rendering."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'title': 'Student Council', 'description': 'Council vote', 'status': 'pre_vote', 'participation_status': None}
        ])

        response = client.get('/voter/secure-votes')
        assert response.status_code == 200

    # --- Join Election Route Tests ---
    def test_join_election_active_new_token(self, app, client, mock_db):
        """Branch A: Joining active election generates and mails token."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        fetch_responses = [
            {'status': 'active', 'title': 'City Council'},
            {'email': 'voter@example.com', 'full_name': 'John Voter'},
            None
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        with patch('routes.voter.send_email', return_value=True), \
             patch('routes.voter.log_event'):
            response = client.get('/voter/join/1')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('voter.secure_votes'))

    def test_join_election_already_joined_exception(self, app, client, mock_db):
        """Branch C: Exception on duplicate join attempts."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.execute = MagicMock(side_effect=Exception("Duplicate entry"))

        response = client.get('/voter/join/1')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.secure_votes'))

    # --- Vote Route Tests ---
    def test_vote_ineligible_redirect(self, app, client, mock_db):
        """Branch 1: Ineligible voter redirected to dashboard."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.fetchone = lambda: None

        response = client.get('/voter/vote/1')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.dashboard'))

    def test_vote_already_voted(self, app, client, mock_db):
        """Branch 2: Voter already cast vote in this election."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        fetch_responses = [
            {'id': 1, 'status': 'active', 'participation_status': 'approved'},
            {'id': 99}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        response = client.get('/voter/vote/1')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.dashboard'))

    def test_vote_invalid_token_submission(self, client, mock_db):
        """Branch 3: Invalid token submitted during voting."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        fetch_responses = [
            {'id': 1, 'status': 'active', 'participation_status': 'approved'},
            None, # No existing vote
            None  # Invalid token record
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None
        mock_db.cursor_obj.set_fetchall([])

        with patch('routes.voter.log_event'):
            response = client.post('/voter/vote/1', data={'token': 'WRONG-TOKEN', 'candidate_id': 2})
            assert response.status_code == 200

    def test_vote_expired_token_submission(self, app, client, mock_db):
        """Branch 4: Expired token submitted."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        expired_time = datetime.now() - timedelta(minutes=5)
        fetch_responses = [
            {'id': 1, 'status': 'active', 'participation_status': 'approved'},
            None,
            {'id': 88, 'expires_at': expired_time}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        response = client.post('/voter/vote/1', data={'token': 'EXPI-RED1', 'candidate_id': 2})
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.vote', eid=1))

    def test_vote_successful_submission(self, app, client, mock_db):
        """Branch 5: Valid voting token submits vote and marks token used."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        valid_expiry = datetime.now() + timedelta(minutes=10)
        fetch_responses = [
            {'id': 1, 'status': 'active', 'participation_status': 'approved'},
            None,
            {'id': 88, 'expires_at': valid_expiry}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        with patch('routes.voter.log_event'):
            response = client.post('/voter/vote/1', data={'token': 'VALI-D123', 'candidate_id': 2})
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('voter.dashboard'))
            assert mock_db.is_committed is True

    # --- Profile Route Tests ---
    def test_voter_profile(self, client, mock_db):
        """Statement Coverage: Voter profile and history rendering."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone({'id': 10, 'full_name': 'John Voter', 'email': 'voter@example.com', 'created_at': datetime.now()})
        mock_db.cursor_obj.set_fetchall([])

        response = client.get('/voter/profile')
        assert response.status_code == 200

    # --- Resend Token Route Tests ---
    def test_resend_token_success(self, app, client, mock_db):
        """Branch 1: Resending token for active approved election."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        fetch_responses = [
            {'title': 'General Election', 'participation_status': 'approved', 'email': 'voter@example.com', 'full_name': 'John Voter'},
            {'id': 88}
        ]
        mock_db.cursor_obj.fetchone = lambda: fetch_responses.pop(0) if fetch_responses else None

        with patch('routes.voter.send_email', return_value=True), \
             patch('routes.voter.log_event'):
            response = client.post('/voter/resend-token/1')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('voter.vote', eid=1))
            assert mock_db.is_committed is True
