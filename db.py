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
    """Initializes the database by creating it and running the schema.sql script."""
    try:
        # Connect to MySQL without specifying a database first
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '')
        )
        cursor = connection.cursor()
        
        # Create database if not exists
        db_name = os.getenv('DB_NAME', 'secure_vote')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")
        
        # Run schema script
        if os.path.exists('schema.sql'):
            with open('schema.sql', 'r') as f:
                schema_script = f.read()
                # Split commands by semicolon to execute individually
                commands = schema_script.split(';')
                for command in commands:
                    if command.strip():
                        cursor.execute(command)
            connection.commit()
            print("Database initialized successfully.")
        else:
            print("schema.sql not found.")
            
        cursor.close()
        connection.close()
    except Error as e:
        print(f"Error while initializing database: {e}")

if __name__ == '__main__':
    init_db()
