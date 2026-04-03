# AuthVote Database Integration Guide

This document explains how the MySQL database is integrated into the AuthVote Flask application, including configuration, connection handling, and execution patterns.

## 1. The Configuration Layer (`.env`)
Database credentials are kept outside of the code for security. The application looks for a `.env` file with the following keys:
- `DB_HOST`: Address of the database server (usually `localhost`).
- `DB_USER`: Database username (e.g., `root`).
- `DB_PASSWORD`: Database password.
- `DB_NAME`: The target database name (e.g., `authvote`).

## 2. The Connection Factory (`db.py`)
Centralized database management is handled in `db.py`. This ensures a single source of truth for connecting to MySQL.

### Core Function: `get_db_connection()`
This function uses the `mysql-connector-python` library to bridge the gap between Python and MySQL.
```python
import mysql.connector
import os

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
```

## 3. Schema Management (`schema.sql`)
The database structure is defined in `schema.sql`. It contains the DDL (Data Definition Language) for:
- `users`: Managed by `auth.py`.
- `elections` & `candidates`: Managed by `admin.py`.
- `votes`: Managed by `voter.py`.
- `system_logs`: Managed by the `utils.py` logging utility.

The application automatically runs this schema on every startup (in `app.py`) to ensure the tables exist.

## 4. Execution Pattern in Routes
To interact with the database within a route, the following pattern is used:

1.  **Open Connection**: `conn = get_db_connection()`
2.  **Create Cursor**: `cursor = conn.cursor(dictionary=True)` (The `dictionary=True` flag allows us to access columns by name like `row['email']`).
3.  **Execute Query**: `cursor.execute("SELECT * FROM table WHERE id = %s", (id,))`
4.  **Confirm Changes**: For `INSERT`, `UPDATE`, or `DELETE`, we call `conn.commit()`.
5.  **Close Everything**: `cursor.close()` and `conn.close()` are called to prevent memory leaks and "too many connections" errors in MySQL.

---

## 5. Security Features
- **SQL Injection Prevention**: We never use f-strings or string concatenation for queries. We always use parameterized queries (`%s`) to let the MySQL driver handle safe escaping.
- **Credential Masking**: Secrets are loaded from the environment, not hardcoded.
- **Relational Constraints**: Foreign keys (e.g., `user_id` in `votes`) ensure that a vote cannot be cast by a non-existent user.
