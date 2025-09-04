"""
User-aware query helpers for multi-user bookkeeping app
All database queries should be filtered by current user
"""

from flask_login import current_user
from models import db, Transaction, TransactionCode, Document, AppSettings

class UserDataManager:
    """Helper class for user-aware database operations"""
    
    @staticmethod
    def get_user_transactions(status=None, category=None):
        """Get transactions for current user with optional filters"""
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        if status == 'reconciled':
            query = query.join(TransactionCode)
        elif status == 'unreconciled':
            query = query.outerjoin(TransactionCode).filter(TransactionCode.id == None)
        
        if category:
            query = query.join(TransactionCode).filter(TransactionCode.category_name == category.title())
        
        return query
    
    @staticmethod
    def get_user_transaction_codes():
        """Get all transaction codes for current user"""
        return TransactionCode.query.filter_by(user_id=current_user.id)
    
    @staticmethod
    def get_user_documents():
        """Get all documents for current user"""
        return Document.query.filter_by(user_id=current_user.id)
    
    @staticmethod
    def create_user_transaction(data):
        """Create a new transaction for current user"""
        transaction = Transaction(**data)
        transaction.user_id = current_user.id
        db.session.add(transaction)
        return transaction
    
    @staticmethod
    def create_user_transaction_code(transaction_id, data):
        """Create a transaction code for current user"""
        code = TransactionCode(**data)
        code.user_id = current_user.id
        code.transaction_id = transaction_id
        db.session.add(code)
        return code
    
    @staticmethod
    def create_user_document(transaction_id, data):
        """Create a document for current user"""
        document = Document(**data)
        document.user_id = current_user.id
        document.transaction_id = transaction_id
        db.session.add(document)
        return document
    
    @staticmethod
    def get_user_statistics():
        """Get dashboard statistics for current user"""
        # Total transactions
        total_transactions = Transaction.query.filter_by(user_id=current_user.id).count()
        
        # Reconciled (have transaction codes)
        reconciled = db.session.query(Transaction).filter_by(user_id=current_user.id)\
            .join(TransactionCode).count()
        
        # Unreconciled
        unreconciled = total_transactions - reconciled
        
        return {
            'total_transactions': total_transactions,
            'reconciled_transactions': reconciled,
            'unreconciled_transactions': unreconciled
        }
    
    @staticmethod
    def get_user_upload_path():
        """Get current user's upload directory"""
        return current_user.upload_path if current_user.is_authenticated else 'uploads'

# Decorator to ensure user data isolation
def user_data_required(f):
    """Decorator to ensure current user context for data operations"""
    from functools import wraps
    from flask_login import login_required
    
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function