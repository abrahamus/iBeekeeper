from datetime import datetime, timezone
from . import db

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Nullable for migration
    filename = db.Column(db.String(255), nullable=False, index=True)  # Index for filename searches
    file_path = db.Column(db.String(500), nullable=False, unique=True)  # Unique constraint and index for file path
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # Index for date sorting
    file_size = db.Column(db.Integer)  # Size in bytes
    
    def __repr__(self):
        return f'<Document {self.id}: {self.filename}>'
    
    @property
    def file_size_mb(self):
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0