import pytest
from unittest.mock import MagicMock
from flask import session

class TestResultsRoutesWhiteBox:
    """White-box structural & path test suite for routes/results.py."""

    def test_all_results_as_voter(self, client, mock_db):
        """Branch B: Voter views closed election results list."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'title': 'Completed Election', 'status': 'closed', 'total_votes': 150}
        ])

        response = client.get('/results/')
        assert response.status_code == 200
        assert "('closed')" in mock_db.cursor_obj.last_executed

    def test_all_results_as_admin(self, client, mock_db):
        """Branch A: Admin views active and closed election results list."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'title': 'Active Election', 'status': 'active', 'total_votes': 45}
        ])

        response = client.get('/results/')
        assert response.status_code == 200
        assert "('active', 'closed')" in mock_db.cursor_obj.last_executed

    def test_view_election_not_found(self, client, mock_db):
        """Branch 1: Non-existent election returns 404."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone(None)

        response = client.get('/results/999')
        assert response.status_code == 404
        assert b"Election results not available." in response.data

    def test_view_election_active_hidden_from_voter(self, client, mock_db):
        """Branch 2: Active election results hidden from voter (403 Forbidden)."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone({'id': 1, 'status': 'active', 'title': 'Ongoing Poll'})

        response = client.get('/results/1')
        assert response.status_code == 403
        assert b"Results are hidden until the election officially closes." in response.data

    def test_view_election_closed_with_winner_calculation(self, client, mock_db):
        """Branch 3: Closed election rendering with candidate percentages and winner detection."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone({'id': 1, 'status': 'closed', 'title': 'Finished Poll'})
        mock_db.cursor_obj.set_fetchall([
            {'id': 101, 'name': 'Candidate A', 'vote_count': 30},
            {'id': 102, 'name': 'Candidate B', 'vote_count': 70}
        ])

        response = client.get('/results/1')
        assert response.status_code == 200

    def test_view_election_closed_zero_votes_no_winner(self, client, mock_db):
        """Branch 3 Subpath: Closed election with zero votes returns no winner cleanly."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone({'id': 1, 'status': 'closed', 'title': 'Finished Poll No Votes'})
        mock_db.cursor_obj.set_fetchall([
            {'id': 101, 'name': 'Candidate A', 'vote_count': 0},
            {'id': 102, 'name': 'Candidate B', 'vote_count': 0}
        ])

        response = client.get('/results/1')
        assert response.status_code == 200

    def test_results_api_unauthorized_voter_active(self, client, mock_db):
        """Branch 1: API returns 403 when voter attempts to fetch active election stats."""
        with client.session_transaction() as sess:
            sess['user_id'] = 10
            sess['role'] = 'voter'

        mock_db.cursor_obj.set_fetchone({'status': 'active'})

        response = client.get('/results/api/1')
        assert response.status_code == 403
        assert response.get_json()['error'] == 'Unauthorized'

    def test_results_api_success(self, client, mock_db):
        """Branch 2: API returns JSON payload for election results."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        mock_db.cursor_obj.set_fetchone({'status': 'active'})
        mock_db.cursor_obj.set_fetchall([
            {'id': 1, 'name': 'Alice', 'vote_count': 15}
        ])

        response = client.get('/results/api/1')
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['election_id'] == 1
        assert json_data['total_votes'] == 15
        assert len(json_data['candidates']) == 1
        assert json_data['candidates'][0]['percentage'] == 100.0
