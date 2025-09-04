from models import db
from sqlalchemy.orm import validates
import json

class AppSettings(db.Model):
    __tablename__ = 'app_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Nullable for migration
    setting_key = db.Column(db.String(100), nullable=False, index=True)  # Removed unique constraint
    setting_value = db.Column(db.Text, nullable=True)  # Store as JSON string for complex values
    is_encrypted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    @validates('setting_key')
    def validate_setting_key(self, key, value):
        """Validate setting key format"""
        if not value or len(value.strip()) == 0:
            raise ValueError("Setting key cannot be empty")
        return value.strip().upper()
    
    def set_value(self, value):
        """Set setting value, converting to JSON if needed"""
        if isinstance(value, (dict, list, bool)) or value is None:
            self.setting_value = json.dumps(value)
        else:
            self.setting_value = str(value)
    
    def get_value(self, default=None):
        """Get setting value, parsing JSON if needed"""
        if self.setting_value is None:
            return default
        
        # Try to parse as JSON first
        try:
            return json.loads(self.setting_value)
        except (json.JSONDecodeError, TypeError):
            # Handle legacy boolean strings for backward compatibility
            if self.setting_value.lower() == 'true':
                return True
            elif self.setting_value.lower() == 'false':
                return False
            # Return as string if not valid JSON and not a boolean
            return self.setting_value
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a setting value by key (backwards compatibility - uses first found)"""
        setting = AppSettings.query.filter_by(setting_key=key.upper()).first()
        return setting.get_value(default) if setting else default
    
    @staticmethod
    def set_setting(key, value):
        """Set a setting value by key (backwards compatibility - updates first found)"""
        setting = AppSettings.query.filter_by(setting_key=key.upper()).first()
        if setting:
            setting.set_value(value)
            setting.updated_at = db.func.current_timestamp()
        else:
            setting = AppSettings(setting_key=key.upper())
            setting.set_value(value)
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @staticmethod
    def get_user_setting(user_id, key, default=None):
        """Get a setting value by key for specific user"""
        setting = AppSettings.query.filter_by(setting_key=key.upper(), user_id=user_id).first()
        return setting.get_value(default) if setting else default
    
    @staticmethod
    def set_user_setting(user_id, key, value):
        """Set a setting value by key for specific user"""
        setting = AppSettings.query.filter_by(setting_key=key.upper(), user_id=user_id).first()
        if setting:
            setting.set_value(value)
            setting.updated_at = db.func.current_timestamp()
        else:
            setting = AppSettings(setting_key=key.upper(), user_id=user_id)
            setting.set_value(value)
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @staticmethod
    def get_wise_config():
        """Get Wise API configuration"""
        return {
            'api_url': AppSettings.get_setting('WISE_API_URL', 'https://api.wise.com'),
            'api_token': AppSettings.get_setting('WISE_API_TOKEN', ''),
            'entity_number': AppSettings.get_setting('WISE_ENTITY_NUMBER', ''),
            'is_sandbox': AppSettings.get_setting('WISE_SANDBOX_MODE', False)
        }
    
    @staticmethod
    def set_wise_config(api_url, api_token, entity_number, is_sandbox=False):
        """Set Wise API configuration"""
        AppSettings.set_setting('WISE_API_URL', api_url)
        AppSettings.set_setting('WISE_API_TOKEN', api_token)
        AppSettings.set_setting('WISE_ENTITY_NUMBER', entity_number)
        AppSettings.set_setting('WISE_SANDBOX_MODE', is_sandbox)
    
    def __repr__(self):
        return f'<AppSettings {self.setting_key}: {self.setting_value[:50] if self.setting_value else None}>'