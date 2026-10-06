import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure root app directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app

class MockCursor:
    def __init__(self, dictionary=False):
        self.dictionary = dictionary
        self._fetchone_data = None
        self._fetchall_data = []
        self.last_executed = None
        self.last_params = None

    def set_fetchone(self, data):
        self._fetchone_data = data

    def set_fetchall(self, data):
        self._fetchall_data = data

    def execute(self, query, params=None):
        self.last_executed = query
        self.last_params = params

    def fetchone(self):
        if callable(self._fetchone_data):
            return self._fetchone_data()
        return self._fetchone_data

    def fetchall(self):
        if callable(self._fetchall_data):
            return self._fetchall_data()
        return self._fetchall_data

    def close(self):
        pass

class MockConnection:
    def __init__(self):
        self.cursor_obj = MockCursor()
        self.is_committed = False
        self.is_rolled_back = False

    def cursor(self, dictionary=False):
        self.cursor_obj.dictionary = dictionary
        return self.cursor_obj

    def commit(self):
        self.is_committed = True

    def rollback(self):
        self.is_rolled_back = True

    def is_connected(self):
        return True

    def close(self):
        pass

@pytest.fixture
def app():
    """Create and configure a Flask app instance for testing."""
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test_secret_key_12345',
        'WTF_CSRF_ENABLED': False
    })
    return test_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's CLI commands."""
    return app.test_cli_runner()

@pytest.fixture
def mock_db():
    """Fixture that patches get_db_connection and yields a MockConnection."""
    mock_conn = MockConnection()
    with patch('db.get_db_connection', return_value=mock_conn), \
         patch('routes.auth.get_db_connection', return_value=mock_conn), \
         patch('routes.admin.get_db_connection', return_value=mock_conn), \
         patch('routes.voter.get_db_connection', return_value=mock_conn), \
         patch('routes.results.get_db_connection', return_value=mock_conn):
        yield mock_conn
