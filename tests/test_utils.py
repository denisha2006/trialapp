import pytest
from unittest.mock import patch, MagicMock
import urllib.error
from utils import (
    clean_image_url,
    generate_otp,
    send_email,
    hash_password,
    check_password,
    generate_voting_token,
    hash_token,
    log_event
)

class TestUtilsWhiteBox:
    """White-box structural test suite for utils.py module."""

    # --- clean_image_url Tests ---
    def test_clean_image_url_empty_or_none(self):
        """Branch: empty/None input handling."""
        assert clean_image_url(None) == ''
        assert clean_image_url('') == ''
        assert clean_image_url('   ') == ''

    def test_clean_image_url_google_imgres_valid(self):
        """Branch 1: Google Images imgres link with imgurl query parameter."""
        google_url = "https://www.google.com/imgres?imgurl=https%3A%2F%2Fexample.com%2Fphoto.jpg&imgrefurl=https%3A%2F%2Fexample.com"
        result = clean_image_url(google_url)
        assert result == "https://example.com/photo.jpg"

    def test_clean_image_url_google_imgres_malformed(self):
        """Branch 1 Exception/Fallback: Google link without imgurl parameter."""
        google_url = "https://www.google.com/imgres?otherparam=123"
        result = clean_image_url(google_url)
        assert result == google_url

    @pytest.mark.parametrize("ext", ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif'])
    def test_clean_image_url_direct_extensions(self, ext):
        """Branch 2: Direct image URL extension match."""
        direct_url = f"https://cdn.example.com/images/candidate{ext}"
        result = clean_image_url(direct_url)
        assert result == direct_url

    def test_clean_image_url_fetch_content_type_image(self):
        """Branch 3 Subpath: Page returning image Content-Type directly."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = 'image/jpeg'
        mock_response.__enter__.return_value = mock_response

        with patch('urllib.request.urlopen', return_value=mock_response):
            url = "https://example.com/dynamic-image-endpoint"
            result = clean_image_url(url)
            assert result == url

    def test_clean_image_url_og_image_meta_tag_absolute(self):
        """Branch 3 Subpath: Extracting og:image meta tag with http URL."""
        html_content = '''
        <html>
            <head>
                <meta property="og:image" content="https://example.com/assets/og_banner.png" />
            </head>
        </html>
        '''.encode('utf-8')

        mock_response = MagicMock()
        mock_response.headers.get.return_value = 'text/html'
        mock_response.read.return_value = html_content
        mock_response.__enter__.return_value = mock_response

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = clean_image_url("https://example.com/page")
            assert result == "https://example.com/assets/og_banner.png"

    def test_clean_image_url_og_image_protocol_relative(self):
        """Branch 3 Subpath: Extracting og:image with // protocol-relative URL."""
        html_content = '''
        <html>
            <head>
                <meta name="twitter:image" content="//cdn.example.com/pic.jpg" />
            </head>
        </html>
        '''.encode('utf-8')

        mock_response = MagicMock()
        mock_response.headers.get.return_value = 'text/html'
        mock_response.read.return_value = html_content
        mock_response.__enter__.return_value = mock_response

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = clean_image_url("https://example.com/page")
            assert result == "https://cdn.example.com/pic.jpg"

    def test_clean_image_url_fallback_img_tag(self):
        """Branch 3 Subpath: Fallback to non-icon img tag when meta tags are absent."""
        html_content = '''
        <html>
            <body>
                <img src="/assets/site_logo.png" />
                <img src="https://example.com/candidate_photo.png" />
            </body>
        </html>
        '''.encode('utf-8')

        mock_response = MagicMock()
        mock_response.headers.get.return_value = 'text/html'
        mock_response.read.return_value = html_content
        mock_response.__enter__.return_value = mock_response

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = clean_image_url("https://example.com/article")
            assert result == "https://example.com/candidate_photo.png"

    def test_clean_image_url_exception_fallback(self):
        """Branch 3 Exception Path: Network failure/HTTP error fallback."""
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            url = "https://invalid-domain-test.com/page"
            result = clean_image_url(url)
            assert result == url

    # --- generate_otp Tests ---
    def test_generate_otp_structure(self):
        """Statement & Decision Coverage: OTP generation format and randomness."""
        otp1 = generate_otp()
        otp2 = generate_otp()
        assert len(otp1) == 6
        assert otp1.isdigit()
        assert len(otp2) == 6
        assert otp2.isdigit()

    # --- send_email Tests ---
    def test_send_email_success(self, app):
        """Branch 1: Successful email sending via Flask-Mail."""
        with app.app_context():
            with patch('utils.mail.send') as mock_send:
                result = send_email("voter@example.com", "Test Subject", "Body Content")
                assert result is True
                assert mock_send.called

    def test_send_email_failure_fallback(self, app):
        """Branch 2: Email sending exception handling & console fallback."""
        with app.app_context():
            with patch('utils.mail.send', side_effect=Exception("SMTP Connection Error")):
                result = send_email("voter@example.com", "Test Subject", "Body Content")
                assert result is False

    # --- Password Hashing Tests ---
    def test_hash_and_check_password(self, app):
        """Statement & Decision Coverage: Bcrypt password hashing and verification."""
        with app.app_context():
            plain_pass = "SecurePass123!"
            hashed = hash_password(plain_pass)
            
            assert hashed != plain_pass
            assert len(hashed) > 0
            assert check_password(hashed, plain_pass) is True
            assert check_password(hashed, "WrongPass123!") is False

    # --- Voting Token Tests ---
    def test_generate_voting_token_format(self):
        """Structure & Boundary Check: Voting token 9-char format (XXXX-XXXX)."""
        token = generate_voting_token(user_id=1, election_id=10)
        assert len(token) == 9
        assert token[4] == '-'
        parts = token.split('-')
        assert len(parts) == 2
        assert len(parts[0]) == 4 and len(parts[1]) == 4
        assert parts[0].isalnum() and parts[1].isalnum()

    def test_hash_token_sha256(self):
        """Statement Coverage: SHA-256 hashing of tokens."""
        raw_token = "ABCD-1234"
        hashed = hash_token(raw_token)
        assert len(hashed) == 64  # Hex length of SHA-256
        assert hash_token(raw_token) == hashed

    # --- log_event Tests ---
    def test_log_event_successful_insert(self, mock_db):
        """Branch 1: Successful system_logs insertion."""
        log_event(user_id=5, action="LOGIN", description="User logged in", anomaly=0.1)
        assert mock_db.cursor_obj.last_executed is not None
        assert "INSERT INTO system_logs" in mock_db.cursor_obj.last_executed
        assert mock_db.cursor_obj.last_params == (5, "LOGIN", "User logged in", 0.1)
        assert mock_db.is_committed is True

    def test_log_event_null_connection(self):
        """Branch 2: get_db_connection returning None."""
        with patch('db.get_db_connection', return_value=None):
            # Should complete without error
            log_event(user_id=1, action="TEST", description="No DB")

    def test_log_event_db_exception(self, mock_db):
        """Branch 3 Exception Path: Exception raised during execution."""
        mock_db.cursor_obj.execute = MagicMock(side_effect=Exception("Database locked"))
        # Should catch exception and not crash
        log_event(user_id=1, action="FAIL", description="Error scenario")
