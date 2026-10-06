# Pre-Seeded Dummy ID Database Reference (`DUMMY_IDS.md`)

Use these pre-seeded demo ID Numbers when testing Registration and Login on the AuthVote platform.

---

## Pre-Seeded Demo ID Records

| ID Number | Visual Type | Registered Holder Name | Linked Demo Email | Role |
| :--- | :--- | :--- | :--- | :--- |
| `1234-5678-9012` | Aadhaar Card | Deni Arora | `deni@gmail.com` | Admin |
| `ABCDE1234F` | PAN Card | Denish User | `den@gmail.com` | Voter |
| `DL-9988776655` | Driving License | Puffer Fish | `pufferfish@xyz.com` | Admin |
| `9876-5432-1098` | Aadhaar Card | Fisher Tester | `fisher@xyz.com` | Admin |

---

## Dynamic ID Registration

If you enter a new ID number during registration (e.g. `1111-2222-3333` or `XYZ9876A`), the system will automatically register it into the ID database linked to your specified email address.

---

## Universal Email Redirector Notice

> All OTPs (Registration ID OTP, Login Identity OTP, Voting Tokens) dispatched to any email address above are automatically delivered to your single demo inbox configured in `.env` (`arorafen9@gmail.com`), tagged with `[Target: email]` in the email subject.
