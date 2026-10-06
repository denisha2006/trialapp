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
1.  **Request & Approval**: Voter joins an election; status is **automatically** set to `approved`. The system instantly generates a unique **HMAC-SHA256** token if the election is active. This token is securely assigned a strict **15-minute expiration countdown**.
2.  **Hashing**: Only the **hash** of the token is stored (`token_hash`), ensuring that even admins cannot see or use the raw token once it's sent.
3.  **Expiration & Validation**: During the vote phase, the application verifies the token hash and explicitly requires that the 15-minute `expires_at` window has not closed.
4.  **Regeneration**: The voter "Resend Token" mechanism automatically invalidates any old token hash, generates a fresh 64-character hex string, emails the voter, and resets their 15-minute countdown clock entirely without admin intervention.

### C. Live Result Tallying & Blind Voting
The **Live Monitor** uses real-time aggregation for Administrators:
- It bypasses intermediate counters and queries the `votes` table directly for accuracy.
- **Chart.js** horizontally visualizes candidate performance to help admins make data-driven decisions.
- **Blind Voting Security**: Standard voters are structurally blocked via API access roles from viewing *any* results geometry while an election is 'active'. This prevents pre-bias bandwagon effects.

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
