from datetime import datetime, timezone
from . import db

# Association table for many-to-many relationship between transactions and documents
transaction_documents = db.Table('transaction_documents',
    db.Column('transaction_id', db.Integer, db.ForeignKey('transaction.id'), primary_key=True),
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True)
)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Nullable for migration
    date = db.Column(db.Date, nullable=False, index=True)  # Index for date queries
    amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False, index=True)  # Precise decimal for currency
    currency = db.Column(db.String(3), nullable=False, index=True)  # Index for currency grouping
    description = db.Column(db.Text, nullable=False)
    payment_reference = db.Column(db.String(255), index=True)  # Index for duplicate detection
    payee_name = db.Column(db.String(255), index=True)  # Index for filtering and duplicate detection
    merchant = db.Column(db.String(255))
    status = db.Column(db.String(50), default='unmatched', index=True)  # Index for status filtering
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # Index for sorting
    
    # Relationships
    documents = db.relationship('Document', secondary=transaction_documents, backref='transactions')
    transaction_code = db.relationship('TransactionCode', backref='transaction', uselist=False)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        db.Index('idx_transaction_date_amount', 'date', 'amount'),  # For duplicate detection
        db.Index('idx_transaction_date_desc', 'date', 'description'),  # For duplicate detection with description
        db.Index('idx_transaction_currency_date', 'currency', 'date'),  # For currency-specific date queries
        db.Index('idx_transaction_status_date', 'status', 'date'),  # For status filtering with date sorting
    )
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.date} - {self.amount} {self.currency}>'
    
    @property
    def is_coded(self):
        return self.transaction_code is not None
    
    @property
    def has_documents(self):
        return len(self.documents) > 0
    
    @property
    def status_display(self):
        if self.is_coded:
            return 'Reconciled'
        else:
            return 'Unreconciled'