# Updated model modifications for multi-user support

"""
REQUIRED DATABASE SCHEMA CHANGES:

1. Add user_id to existing tables:
   - ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id);
   - ALTER TABLE transaction_codes ADD COLUMN user_id INTEGER REFERENCES users(id);
   - ALTER TABLE documents ADD COLUMN user_id INTEGER REFERENCES users(id);
   - ALTER TABLE app_settings ADD COLUMN user_id INTEGER REFERENCES users(id);

2. Add indexes for performance:
   - CREATE INDEX idx_transactions_user_id ON transactions(user_id);
   - CREATE INDEX idx_transaction_codes_user_id ON transaction_codes(user_id);
   - CREATE INDEX idx_documents_user_id ON documents(user_id);
   - CREATE INDEX idx_app_settings_user_id ON app_settings(user_id);

3. Update existing models to include user_id relationships:
"""

# Example updates needed for transaction.py:
"""
class Transaction(db.Model):
    # ... existing fields ...
    
    # ADD THIS:
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Update any queries to filter by current user
"""

# Example updates needed for app_settings.py:
"""
class AppSettings(db.Model):
    # ... existing fields ...
    
    # ADD THIS:
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    @staticmethod
    def get_user_setting(user_id, key, default=None):
        setting = AppSettings.query.filter_by(setting_key=key.upper(), user_id=user_id).first()
        return setting.get_value(default) if setting else default
    
    @staticmethod
    def set_user_setting(user_id, key, value):
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
"""