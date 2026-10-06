# Automatic ID Association Reference (`DUMMY_IDS.md`)

In the AuthVote platform, there is no need to pre-seed or maintain a manual fake ID database.

---

## How ID Association Works

1. **On Registration (`/register`)**:
   - The registrant enters their Name, Email, Password, chooses an ID Type (Aadhaar, PAN, Driving License), and enters their **ID Number**.
   - Upon completing 6-digit email OTP verification, the backend **automatically associates and binds the ID Number to the registered user account** in the database.

2. **On Login (`/login`)**:
   - The user logs in with Email, Password, and **ID Number**.
   - The backend confirms that the entered ID Number matches the ID Number bound to the user account, then initiates 2-Step MFA (Captcha + Login Identity OTP).

---

## Universal Email Redirector Notice

> All OTPs (Registration OTP, Login MFA OTP, Voting Tokens) dispatched to any registered email address are automatically delivered to your single demo inbox configured in `.env` (`arorafen9@gmail.com`), tagged with `[Target: email]` in the email subject line.
