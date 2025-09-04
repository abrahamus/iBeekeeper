from datetime import datetime, timezone
from . import db

class TransactionCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Nullable for migration
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False, index=True)  # Index for joins
    category_name = db.Column(db.String(100), nullable=False, index=True)  # Index for category filtering  
    notes = db.Column(db.Text)
    coded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # Index for date sorting
    
    def __repr__(self):
        return f'<TransactionCode {self.id}: {self.category_name}>'