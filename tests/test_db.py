import pytest
from unittest.mock import patch, MagicMock, mock_open
import mysql.connector
from mysql.connector import Error
from db import get_db_connection, init_db

class TestDatabaseWhiteBox:
    """White-box structural test suite for db.py."""

    def test_get_db_connection_success(self):
        """Branch 1: Successful MySQL connection."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch('mysql.connector.connect', return_value=mock_conn):
            conn = get_db_connection()
            assert conn is mock_conn
            assert conn.is_connected() is True

    def test_get_db_connection_failure(self):
        """Branch 2 Exception Path: Connection fails with MySQL Error."""
        with patch('mysql.connector.connect', side_effect=Error("Access denied for user")):
            conn = get_db_connection()
            assert conn is None

    def test_init_db_success(self):
        """Branch 1: Normal database initialization and schema execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        m_open = mock_open(read_data="CREATE TABLE t1 (id INT); CREATE TABLE t2 (id INT);")

        with patch('mysql.connector.connect', return_value=mock_conn), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', m_open):
            init_db()
            assert mock_cursor.execute.called
            assert mock_conn.commit.called
            assert mock_cursor.close.called
            assert mock_conn.close.called

    def test_init_db_missing_schema_file(self):
        """Branch 2: Schema file schema.sql does not exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch('mysql.connector.connect', return_value=mock_conn), \
             patch('os.path.exists', return_value=False):
            init_db()
            assert mock_cursor.execute.call_count == 2  # CREATE DATABASE and USE database
            assert mock_cursor.close.called
            assert mock_conn.close.called

    def test_init_db_exception_handling(self):
        """Branch 3 Exception Path: Error during database creation."""
        with patch('mysql.connector.connect', side_effect=Error("DB Initialization Failed")):
            # Should catch error gracefully and print log
            init_db()
