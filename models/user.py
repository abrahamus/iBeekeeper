from models import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import secrets

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Generate unique user folder for file uploads
    user_folder = db.Column(db.String(32), unique=True, nullable=False)
    
    # User settings (JSON field for flexibility)
    settings = db.Column(db.Text)  # JSON string for user preferences
    
    # Relationships (user owns their data)
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    transaction_codes = db.relationship('TransactionCode', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    app_settings = db.relationship('AppSettings', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.user_folder:
            self.user_folder = secrets.token_urlsafe(16)  # Generate unique folder name
    
    def set_password(self, password):
        """Hash and set user password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property 
    def upload_path(self):
        """Get user's unique upload directory path"""
        return f"uploads/users/{self.user_folder}"
    
    def get_wise_config(self):
        """Get user's Wise API configuration"""
        from models.app_settings import AppSettings
        return {
            'api_url': AppSettings.get_user_setting(self.id, 'WISE_API_URL', 'https://api.wise.com'),
            'api_token': AppSettings.get_user_setting(self.id, 'WISE_API_TOKEN', ''),
            'entity_number': AppSettings.get_user_setting(self.id, 'WISE_ENTITY_NUMBER', ''),
            'is_sandbox': AppSettings.get_user_setting(self.id, 'WISE_SANDBOX_MODE', False)
        }
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.email}>'