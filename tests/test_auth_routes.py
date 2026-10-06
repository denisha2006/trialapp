import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from flask import session, url_for
from utils import hash_password

class TestAuthRoutesWhiteBox:
    """White-box structural & path test suite for routes/auth.py."""

    # --- Register Route Tests ---
    def test_register_get(self, client):
        """Statement Coverage: GET /register renders page."""
        response = client.get('/register')
        assert response.status_code == 200

    def test_register_missing_fields(self, app, client):
        """Branch 1: Missing form fields."""
        response = client.post('/register', data={
            'full_name': 'Test User',
            'email': '',
            'password': 'pass',
            'confirm_password': 'pass',
            'id_number': 'ID123'
        })
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.register'))

    def test_register_password_mismatch(self, app, client):
        """Branch 2: Password and Confirm Password mismatch."""
        response = client.post('/register', data={
            'full_name': 'Test User',
            'email': 'user@example.com',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword!',
            'id_number': 'ID123'
        })
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.register'))

    def test_register_db_error(self, client):
        """Branch 3: Database connection error during registration."""
        with patch('routes.auth.get_db_connection', return_value=None):
            response = client.post('/register', data={
                'full_name': 'Test User',
                'email': 'user@example.com',
                'password': 'Password123!',
                'confirm_password': 'Password123!',
                'id_number': 'ID123'
            })
            assert response.status_code == 302

    def test_register_existing_email(self, app, client, mock_db):
        """Branch 4: Existing user with same email."""
        mock_db.cursor_obj.set_fetchone({'id': 1})
        response = client.post('/register', data={
            'full_name': 'Test User',
            'email': 'existing@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'id_number': 'ID123'
        })
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.register'))

    def test_register_success(self, app, client, mock_db):
        """Branch 5: Successful registration initiating OTP flow."""
        mock_db.cursor_obj.set_fetchone(None)  # Email does not exist
        with patch('routes.auth.send_email', return_value=True):
            response = client.post('/register', data={
                'full_name': 'New Voter',
                'email': 'newvoter@example.com',
                'password': 'Password123!',
                'confirm_password': 'Password123!',
                'role': 'voter',
                'id_number': 'VOTER12345'
            })
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('auth.verify_otp'))

            with client.session_transaction() as sess:
                assert 'pending_registration' in sess
                assert sess['pending_registration']['email'] == 'newvoter@example.com'

    # --- Verify OTP Route Tests ---
    def test_verify_otp_no_session(self, app, client):
        """Branch 1: Accessing verify-otp without pending session."""
        response = client.get('/verify-otp')
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.register'))

    def test_verify_otp_invalid_code(self, client):
        """Branch 2: Entering incorrect OTP code."""
        with client.session_transaction() as sess:
            sess['pending_registration'] = {
                'full_name': 'Test User',
                'email': 'test@example.com',
                'password_hash': 'hash',
                'role': 'voter',
                'id_number': 'ID123',
                'otp': '123456',
                'otp_expires_at': (datetime.now() + timedelta(minutes=10)).isoformat()
            }

        response = client.post('/verify-otp', data={'otp': '999999'})
        assert response.status_code == 200  # Stays on verify_otp page

    def test_verify_otp_success(self, app, client, mock_db):
        """Branch 3: Valid OTP entry creates user in database."""
        with client.session_transaction() as sess:
            sess['pending_registration'] = {
                'full_name': 'Test User',
                'email': 'valid@example.com',
                'password_hash': 'hash123',
                'role': 'voter',
                'id_number': 'ID12345',
                'otp': '654321',
                'otp_expires_at': (datetime.now() + timedelta(minutes=10)).isoformat()
            }

        mock_db.cursor_obj.set_fetchone({'id': 42})
        with patch('routes.auth.log_event'):
            response = client.post('/verify-otp', data={'otp': '654321'})
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('auth.login'))

            with client.session_transaction() as sess:
                assert 'pending_registration' not in sess

    # --- Login Route Tests ---
    def test_login_missing_fields(self, app, client):
        """Branch 1: Login missing required form parameters."""
        response = client.post('/login', data={'email': 'user@example.com', 'password': ''})
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.login'))

    def test_login_invalid_credentials(self, client, mock_db):
        """Branch 3: Invalid user email or password."""
        mock_db.cursor_obj.set_fetchone(None)
        with patch('routes.auth.log_event'):
            response = client.post('/login', data={
                'email': 'nonexistent@example.com',
                'password': 'wrongpassword',
                'id_number': 'ID123'
            })
            assert response.status_code == 200

    def test_login_unverified_user(self, app, client, mock_db):
        """Branch 4: Valid credentials but account is not verified."""
        with app.app_context():
            hashed_pass = hash_password('CorrectPass123!')

        mock_db.cursor_obj.set_fetchone({
            'id': 10,
            'email': 'unverified@example.com',
            'password_hash': hashed_pass,
            'is_verified': 0,
            'id_number': 'ID123'
        })

        response = client.post('/login', data={
            'email': 'unverified@example.com',
            'password': 'CorrectPass123!',
            'id_number': 'ID123'
        })
        assert response.status_code == 302
        with app.test_request_context():
            assert response.location.endswith(url_for('auth.register'))

    def test_login_id_mismatch(self, app, client, mock_db):
        """Branch 5: Registered ID does not match input ID."""
        with app.app_context():
            hashed_pass = hash_password('CorrectPass123!')

        mock_db.cursor_obj.set_fetchone({
            'id': 10,
            'email': 'user@example.com',
            'password_hash': hashed_pass,
            'is_verified': 1,
            'id_number': 'REAL_ID_999'
        })

        with patch('routes.auth.log_event'):
            response = client.post('/login', data={
                'email': 'user@example.com',
                'password': 'CorrectPass123!',
                'id_number': 'WRONG_ID_111'
            })
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('auth.login'))

    def test_login_success_mfa_initiating(self, app, client, mock_db):
        """Branch 7: Successful login credential check initiates MFA session."""
        with app.app_context():
            hashed_pass = hash_password('CorrectPass123!')

        mock_db.cursor_obj.set_fetchone({
            'id': 15,
            'email': 'voter@example.com',
            'password_hash': hashed_pass,
            'is_verified': 1,
            'id_number': 'ID12345'
        })

        with patch('routes.auth.log_event'):
            response = client.post('/login', data={
                'email': 'voter@example.com',
                'password': 'CorrectPass123!',
                'id_number': 'ID12345'
            })
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('auth.mfa_view'))

            with client.session_transaction() as sess:
                assert sess.get('pending_mfa_user_id') == 15

    # --- MFA API Endpoint Tests ---
    def test_get_captcha(self, client):
        """Statement Coverage: Captcha generation API."""
        response = client.get('/api/v1/auth/mfa/captcha')
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'captcha' in json_data
        assert len(json_data['captcha']) == 6

    def test_verify_panel1_unauthorized(self, client):
        """Branch 1: MFA panel 1 verification without session."""
        response = client.post('/api/v1/auth/mfa/verify-panel1', json={'captcha': 'ABCDEF', 'epic_id': 'ID123'})
        assert response.status_code == 401

    def test_verify_panel1_invalid_captcha(self, client, mock_db):
        """Branch 4: Captcha mismatch."""
        with client.session_transaction() as sess:
            sess['pending_mfa_user_id'] = 15
            sess['captcha_code'] = 'SECRET'

        mock_db.cursor_obj.set_fetchone({'id': 15, 'id_number': 'ID123'})
        response = client.post('/api/v1/auth/mfa/verify-panel1', json={'captcha': 'WRONG', 'epic_id': 'ID123'})
        assert response.status_code == 400
        assert 'Invalid Captcha' in response.get_json()['error']

    def test_verify_panel1_success(self, client, mock_db):
        """Branch 6: Successful captcha & ID verification sends Login OTP."""
        with client.session_transaction() as sess:
            sess['pending_mfa_user_id'] = 15
            sess['captcha_code'] = 'MATCH1'

        mock_db.cursor_obj.set_fetchone({
            'id': 15,
            'full_name': 'Test Voter',
            'email': 'voter@example.com',
            'id_number': 'ID123'
        })

        with patch('routes.auth.send_email', return_value=True):
            response = client.post('/api/v1/auth/mfa/verify-panel1', json={'captcha': 'MATCH1', 'epic_id': 'ID123'})
            assert response.status_code == 200
            assert response.get_json()['success'] is True

    def test_verify_otp_endpoint_success(self, client, mock_db):
        """Branch 4: Valid MFA OTP input."""
        with client.session_transaction() as sess:
            sess['pending_mfa_user_id'] = 15

        mock_db.cursor_obj.set_fetchone({
            'id': 15,
            'otp': '123456',
            'otp_expires_at': datetime.now() + timedelta(minutes=5)
        })

        response = client.post('/api/v1/auth/mfa/verify-otp', json={'otp': '123456'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True

    def test_generate_token_promotes_session(self, app, client, mock_db):
        """Branch 4: Token generation promotes pending MFA session to full login session."""
        with client.session_transaction() as sess:
            sess['pending_mfa_user_id'] = 15

        mock_db.cursor_obj.set_fetchone({
            'id': 15,
            'full_name': 'Voter Name',
            'role': 'voter',
            'id_number': 'ID123'
        })

        with patch('routes.auth.log_event'):
            response = client.post('/api/v1/auth/token/generate')
            assert response.status_code == 200
            json_data = response.get_json()
            assert json_data['success'] is True
            assert 'token' in json_data

            with client.session_transaction() as sess:
                assert sess['user_id'] == 15
                assert sess['role'] == 'voter'
                assert 'pending_mfa_user_id' not in sess

    # --- Logout Route Tests ---
    def test_logout(self, app, client):
        """Statement Coverage: Logout clears session and redirects to login."""
        with client.session_transaction() as sess:
            sess['user_id'] = 15

        with patch('routes.auth.log_event'):
            response = client.get('/logout')
            assert response.status_code == 302
            with app.test_request_context():
                assert response.location.endswith(url_for('auth.login'))

            with client.session_transaction() as sess:
                assert 'user_id' not in sess
