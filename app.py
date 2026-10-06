from flask import Flask, render_template
import os
from dotenv import load_dotenv
from db import init_db
from utils import bcrypt, mail
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.voter import voter_bp
from routes.results import results_bp

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'SECUREVOTE_SESSION_SECRET_99!')
    
    # Flask-Mail Configuration
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
    
    # Initialize extensions
    bcrypt.init_app(app)
    mail.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(voter_bp)
    app.register_blueprint(results_bp)
    
    @app.route('/')
    def home():
        return render_template('home.html')
        
    return app

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    
    app = create_app()
    app.run(debug=True, port=int(os.getenv('PORT', 5000)))
