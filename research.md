# AuthVote Architecture & Research Notes (`research.md`)

This document serves as the authoritative research and technical architecture reference for the **AuthVote** platform. It documents research on online voting system security, identity verification state machines, database normalization, and test email redirection patterns.

---

## 1. Architectural Blueprint & Technical Stack

### Tech Stack
- **Backend Framework**: Python 3.x / Flask 3.0
- **Database**: MySQL 8.0 / MariaDB with `mysql-connector-python`
- **Security & Crypto**: `flask-bcrypt` (password hashing), SHA-256 (voting token hashing)
- **Email Dispatch**: `flask-mail` with Universal Email Redirector pattern
- **Frontend Layer**: Vanilla HTML5, Vanilla JavaScript, CSS3 (Dark Glassmorphism Design System)

---

## 2. Automatic ID Association Mechanism

For demonstration testing, the system automatically associates the user's `id_number` with their registered user account during registration. This eliminates the need to maintain static pre-made fake ID records.

### Unified Backend Storage Pattern
The ID Type dropdown on the frontend (Aadhaar, PAN, Driving License) serves visual UI selection purposes. In the backend database, all IDs are stored and validated as a single unified `id_number` (`VARCHAR(50)`).

---

## 3. Simplified Authentication State Machine

```
                  ┌─────────────────────────────────────────┐
                  │           REGISTRATION FLOW             │
                  └─────────────────────────────────────────┘
                                       │
            User submits Name, Email, Password, ID Number
                                       │
                      Dispatches Registration OTP
                                       │
                       User enters 6-digit OTP
                                       │
                  Account Created & ID Associated!
```

```
                  ┌─────────────────────────────────────────┐
                  │              LOGIN FLOW                 │
                  └─────────────────────────────────────────┘
                                       │
            User submits Email, Password, ID Number
                                       │
               Verifies Password & Registered User ID Match
                                       │
                         Redirects to `/mfa` (Step 1)
                                       │
                  User solves Captcha & requests Login OTP
                                       │
                      Dispatches Login Identity OTP
                                       │
                       User enters 6-digit Login OTP
                                       │
                       Authorized Session (Dashboard)
```

---

## 4. Universal Email Redirector Pattern

In a demonstration environment, evaluators test with multiple simulated voter accounts (`deni@gmail.com`, `den@gmail.com`, `fisher@xyz.com`). Requiring access to multiple real email inboxes breaks the demonstration flow.

### Implementation Pattern
The `send_email()` utility wraps `flask-mail`. When dispatching any message (Registration OTP, Login MFA OTP, Voting Token):
1. Reads `UNIVERSAL_REDIRECT_EMAIL` or `MAIL_DEFAULT_SENDER` from environment.
2. Directs the email message to `actual_recipient` (the tester's configured email address).
3. Modifies the subject header to include `[Target: original_email]`.
4. Enables 100% single-inbox testing across all demo user accounts.

---

## 5. Lessons Learned & Refactoring Rules
1. **Streamlined Testing**: Automatic ID association during registration enables frictionless evaluation with any arbitrary test ID.
2. **Single-Inbox Redirection**: Universal Email Redirector allows testing multi-user workflows without juggling real email accounts.
3. **Traceability**: All verification attempts (success and failure) are recorded in `mfa_audit_logs` and `system_logs`.
