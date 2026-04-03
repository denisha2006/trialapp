# AuthVote Technical Reference

AuthVote is a high-security, blockchain-inspired voting platform built with Python, Flask, and MySQL. This document serves as a technical reference for its core operations and security architecture.

## 1. System Architecture
- **Backend**: Flask (Python) with a modular blueprint architecture.
- **Database**: MySQL for structured data and relational integrity.
- **Styling**: Modern, premium dark-themed CSS with glassmorphism components.
- **Security**: Cryptographic token-based voting and event-driven audit logging.

## 2. Core Working Logic

### A. Voter Registration & Authentication
- **Secure Hashing**: Passwords are never stored in plain text. We use `Flask-Bcrypt` (bcrypt hashing) for industry-standard credential security.
- **Session Management**: Secure signed cookies manage user states and roles (Admin vs. Voter).

### B. Voting Token Lifecycle (HMAC Security)
To prevent fraud and duplicate voting, AuthVote uses a **Cryptographic Token System**:
1.  **Request**: Voter joins an election; status set to `pending`.
2.  **Approval**: Admin reviews and approves; the system generates a unique **HMAC-SHA256** token.
3.  **Hashing**: Only the **hash** of the token is stored (`token_hash`), ensuring that even admins cannot see or use the raw token once it's sent.
4.  **Regeneration**: The "Resend Token" feature automatically invalidates the old hash and generates a fresh 64-character hex string for the voter.

### C. Live Result Tallying
The **Live Monitor** uses real-time aggregation:
- It bypasses intermediate counters and queries the `votes` table directly for accuracy.
- **Chart.js** horizontally visualizes candidate performance to help admins make data-driven decisions.

### D. Security & Audit Logging
The `utils.log_event` function records every critical action:
- `VOTE_CAST`, `LOGIN_SUCCESS`, `INVALID_TOKEN`, etc.
- **Anomaly Detection**: Failed vote attempts (bad tokens) are flagged with an anomaly score (0.6+) to alert admins of potential tampering.

---

## 3. Database Summary
- `users`: Credentials, Voter IDs, and roles.
- `elections`: Metadata (start/end times, description) and status (`pre_vote`, `active`, `closed`).
- `candidates`: Profiles linked to specific elections.
- `voting_tokens`: Cryptographically-linked access keys for voters.
- `system_logs`: Full audit trail of application usage.
