import pytest
from flask import session, url_for
from decorators import login_required, admin_required

class TestDecoratorsWhiteBox:
    """White-box structural test suite for decorators.py."""

    def test_login_required_unauthenticated(self, app):
        """Path 1: User not logged in -> redirect to login with flash warning."""
        @app.route('/test-login-protected')
        @login_required
        def dummy_route():
            return "Secret Area"

        client = app.test_client()
        response = client.get('/test-login-protected')
        
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.login'))

    def test_login_required_authenticated(self, app):
        """Path 2: User logged in -> access granted."""
        @app.route('/test-login-protected-success')
        @login_required
        def dummy_route():
            return "Secret Area"

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = 100

        response = client.get('/test-login-protected-success')
        assert response.status_code == 200
        assert response.data.decode() == "Secret Area"

    def test_admin_required_unauthenticated(self, app):
        """Path 1: No active session -> redirect to voter.dashboard with flash danger."""
        @app.route('/test-admin-protected')
        @admin_required
        def dummy_admin_route():
            return "Admin Area"

        client = app.test_client()
        response = client.get('/test-admin-protected')
        
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.dashboard'))

    def test_admin_required_non_admin_role(self, app):
        """Path 2: User logged in as voter -> access denied, redirect to voter.dashboard."""
        @app.route('/test-admin-protected-voter')
        @admin_required
        def dummy_admin_route():
            return "Admin Area"

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = 101
            sess['role'] = 'voter'

        response = client.get('/test-admin-protected-voter')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('voter.dashboard'))

    def test_admin_required_authorized_admin(self, app):
        """Path 3: User logged in as admin -> access granted."""
        @app.route('/test-admin-protected-success')
        @admin_required
        def dummy_admin_route():
            return "Admin Area"

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = 102
            sess['role'] = 'admin'

        response = client.get('/test-admin-protected-success')
        assert response.status_code == 200
        assert response.data.decode() == "Admin Area"
