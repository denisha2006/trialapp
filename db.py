import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'secure_vote')
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    """Initializes the database and creates required tables."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '')
        )
        cursor = connection.cursor()
        
        db_name = os.getenv('DB_NAME', 'secure_vote')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        cursor.execute(f"USE `{db_name}`")
        
        if os.path.exists('schema.sql'):
            with open('schema.sql', 'r') as f:
                schema_script = f.read()
                statements = [s.strip() for s in schema_script.split(';') if s.strip()]
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()

        print("Database initialized successfully.")
        cursor.close()
        connection.close()
    except Error as e:
        print(f"Error while initializing database: {e}")

if __name__ == '__main__':
    init_db()
