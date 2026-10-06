import random
import string
import hashlib
import hmac
import os
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message

bcrypt = Bcrypt()
mail = Mail()

from urllib.parse import parse_qs, urlparse, urljoin
import urllib.request
import re

def clean_image_url(url):
    """Cleans up and resolves direct image links from image URLs, Google search links, or web page links."""
    if not url:
        return ''
    url = url.strip()
    
    # 1. Google Images imgres link
    if 'google.com/imgres' in url:
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'imgurl' in params and params['imgurl']:
                return params['imgurl'][0]
        except Exception:
            pass

    # 2. Direct image extension check
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif']):
        return url

    # 3. If it's a web page URL (e.g., Shopify product page, news link), fetch page and extract og:image meta tag
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            content_type = resp.headers.get('Content-Type', '').lower()
            if 'image/' in content_type:
                return url
            
            html = resp.read().decode('utf-8', errors='ignore')
            
            # Find og:image or twitter:image meta tags
            og_match = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not og_match:
                og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']', html, re.IGNORECASE)
                
            if og_match:
                img_src = og_match.group(1).strip()
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif not img_src.startswith('http'):
                    img_src = urljoin(url, img_src)
                return img_src

            # Fallback to first large img src on page
            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for src in img_matches:
                src_clean = src.strip()
                if not any(skip in src_clean.lower() for skip in ['logo', 'icon', 'pixel', 'avatar', 'loader', 'blank', 'svg']):
                    if src_clean.startswith('//'):
                        src_clean = 'https:' + src_clean
                    elif not src_clean.startswith('http'):
                        src_clean = urljoin(url, src_clean)
                    return src_clean
    except Exception as e:
        print(f"[IMAGE RESOLVER ERROR] Could not extract image from page '{url}': {e}")

    return url

def generate_otp():
    """Generates a 6-digit random OTP."""
    return ''.join(random.choices(string.digits, k=6))

def send_email(to, subject, body, html=None):
    """
    Universal Email Redirector:
    Redirects all outbound messages to the designated single demo inbox (MAIL_DEFAULT_SENDER)
    so all OTPs across all registered test emails can be tested from a single inbox.
    """
    try:
        sender = os.getenv('MAIL_DEFAULT_SENDER', 'arorafen9@gmail.com')
        # Universal Redirector Target
        redirect_target = os.getenv('UNIVERSAL_REDIRECT_EMAIL') or sender
        
        # Format subject line with original target indicator
        redirect_subject = f"[Target: {to}] {subject}"
        
        # Create Flask-Mail Message dispatched to redirect_target
        msg = Message(redirect_subject, recipients=[redirect_target], body=body, html=html, sender=sender)
        mail.send(msg)
        print(f"[UNIVERSAL REDIRECTOR] Redirected email intended for '{to}' -> Delivered to '{redirect_target}'")
        return True
    except Exception as e:
        print(f"[MAIL ERROR] Failed to send email: {e}")
        print(f"--- MOCK EMAIL INTERCEPT ---")
        print(f"Original Target: {to}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        print(f"----------------------------")
        return False

def hash_password(password):
    """Hashes a password using Bcrypt."""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(hashed_password, password):
    """Checks a password against its hash."""
    return bcrypt.check_password_hash(hashed_password, password)

def generate_voting_token(user_id, election_id):
    """Generates a shorter, user-friendly 9-character voting token."""
    chars = string.ascii_uppercase + string.digits
    raw = ''.join(random.choices(chars, k=8))
    return f"{raw[:4]}-{raw[4:]}"

def hash_token(token):
    """Hashes a raw token with SHA-256 for database storage."""
    return hashlib.sha256(token.encode()).hexdigest()

def log_event(user_id, action, description, anomaly=0.0):
    """Logs a system event to the database."""
    from db import get_db_connection
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_logs (user_id, action, description, anomaly) 
            VALUES (%s, %s, %s, %s)
        """, (user_id, action, description, anomaly))
        conn.commit()
    except Exception as e:
        print(f"[ERROR] Logging event: {e}")
    finally:
        cursor.close()
        conn.close()
