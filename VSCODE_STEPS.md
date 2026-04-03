# Manual Setup & Run Guide (VS Code)

This guide provides step-by-step instructions for running the AuthVote application on your local machine using Visual Studio Code and XAMPP.

## 1. Prerequisites
- **Python**: Ensure Python 3.8 or higher is installed (`python --version`).
- **XAMPP / MySQL**: Ensure MySQL is running on your system (Default port 3306).
- **VS Code Extensions**: (Recommended)
  - **Python Extension Pack** (Microsoft)
  - **MySQL** (cweijan) for database management.

---

## 2. Environment Setup

### A. Open Project
1.  Open VS Code.
2.  Go to `File` > `Open Folder...` and select the `trialapp` directory.

### B. Virtual Environment (Optional but Recommended)
1.  Open the integrated terminal in VS Code (`Ctrl + ``).
2.  Run: `python -m venv venv`
3.  Activate it:
    - **Windows**: `.\venv\Scripts\activate`
    - **Mac/Linux**: `source venv/bin/activate`

### C. Install Dependencies
1.  In the terminal, run:
    ```bash
    pip install -r requirements.txt
    ```

---

## 3. Configuration

### A. Environment Variables (`.env`)
1.  Locate the `.env.example` file and rename it to `.env`.
2.  Update the database credentials:
    - `DB_HOST=localhost`
    - `DB_USER=root` (or your MySQL username)
    - `DB_PASSWORD=` (leave blank if using default XAMPP)
    - `DB_NAME=authvote`
3.  Set a random `SECRET_KEY` and `HMAC_KEY` for security.

### B. Database Initialization
1.  Open XAMPP Control Panel and start **MySQL**.
2.  Create a new database named `authvote` using phpMyAdmin or the VS Code MySQL extension.
3.  Import the schema:
    ```bash
    mysql -u root authvote < schema.sql
    ```

---

## 4. Running the Application

1.  In the VS Code terminal, execute:
    ```bash
    python app.py
    ```
2.  The application will be accessible at: `http://127.0.0.1:5000`

---

## 5. Accessing the Admin Console
Since there is no "register as admin" link for security, use the following default admin credentials (if created from initial population):

- **Username**: `admin@authvote.com`
- **Password**: `admin123`

*Note: You can also manually set a user's `role` to 'admin' in the `users` table via MySQL.*
