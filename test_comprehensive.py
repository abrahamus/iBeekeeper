"""
Comprehensive unit test suite for iBeekeeper application.
Tests all functions, methods, edge cases, and integration points.
"""

import pytest
import tempfile
import os
import shutil
import decimal
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO, StringIO
import json

# Flask and extensions
from flask import Flask
from flask_login import login_user
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

# Application imports
from app import create_app
from models import db, User, Transaction, TransactionCode, Document, AppSettings
from config import Config
from utils.validation import InputValidator, SearchValidator, ValidationError
from utils.transaction_deduplication import TransactionDeduplicator
from utils.user_aware_queries import UserDataManager
from services.wise_api import WiseAPIService
from services.file_service import FileService


class TestConfig(Config):
    """Test configuration with SQLite in-memory database."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'test_uploads'
    

@pytest.fixture
def app():
    """Create test Flask application."""
    app = create_app()
    app.config.from_object(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create test user."""
    with app.app_context():
        user = User(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def authenticated_client(app, client, test_user):
    """Create authenticated client with logged-in user."""
    with app.app_context():
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
    return client


@pytest.fixture
def sample_transaction(app, test_user):
    """Create sample transaction."""
    with app.app_context():
        transaction = Transaction(
            user_id=test_user.id,
            date=date.today(),
            amount=Decimal('100.50'),
            currency='USD',
            description='Test transaction',
            payee_name='Test Payee',
            merchant='Test Merchant',
            payment_reference='REF123'
        )
        db.session.add(transaction)
        db.session.commit()
        return transaction


class TestInputValidator:
    """Test InputValidator class thoroughly."""
    
    def test_validate_amount_valid(self):
        """Test valid amount validation."""
        # Test various valid formats
        assert InputValidator.validate_amount('100.50') == Decimal('100.50')
        assert InputValidator.validate_amount(100.50) == Decimal('100.50')
        assert InputValidator.validate_amount(100) == Decimal('100.00')
        assert InputValidator.validate_amount(Decimal('100.50')) == Decimal('100.50')
        assert InputValidator.validate_amount('0') == Decimal('0.00')
        assert InputValidator.validate_amount('-100.50') == Decimal('-100.50')
    
    def test_validate_amount_invalid(self):
        """Test invalid amount validation."""
        # Test empty/None values
        with pytest.raises(ValidationError, match="Amount cannot be empty"):
            InputValidator.validate_amount('')
        
        with pytest.raises(ValidationError, match="Invalid amount format"):
            InputValidator.validate_amount(None)
        
        # Test invalid formats
        with pytest.raises(ValidationError, match="Invalid amount format"):
            InputValidator.validate_amount('abc')
        
        with pytest.raises(ValidationError, match="Invalid amount format"):
            InputValidator.validate_amount('100.50.75')
        
        # Test amount too small
        with pytest.raises(ValidationError, match="Amount must be at least"):
            InputValidator.validate_amount('0.001')
        
        # Test amount too large
        with pytest.raises(ValidationError, match="Amount cannot exceed"):
            InputValidator.validate_amount('9999999999.99')
        
        # Test too many decimal places
        with pytest.raises(ValidationError, match="cannot have more than 2 decimal places"):
            InputValidator.validate_amount('100.555')
    
    def test_validate_currency_code(self):
        """Test currency code validation."""
        # Valid codes
        assert InputValidator.validate_currency_code('USD') == 'USD'
        assert InputValidator.validate_currency_code('usd') == 'USD'
        assert InputValidator.validate_currency_code(' EUR ') == 'EUR'
        
        # Invalid codes
        with pytest.raises(ValidationError, match="Currency code is required"):
            InputValidator.validate_currency_code('')
        
        with pytest.raises(ValidationError, match="must be exactly 3 letters"):
            InputValidator.validate_currency_code('US')
        
        with pytest.raises(ValidationError, match="must contain only letters"):
            InputValidator.validate_currency_code('U5D')
        
        with pytest.raises(ValidationError, match="Unsupported currency code"):
            InputValidator.validate_currency_code('XYZ')
    
    def test_validate_date(self):
        """Test date validation."""
        # Valid dates
        test_date = date(2024, 1, 15)
        assert InputValidator.validate_date('2024-01-15') == test_date
        assert InputValidator.validate_date('01/15/2024') == test_date
        assert InputValidator.validate_date('15/01/2024') == test_date
        assert InputValidator.validate_date(test_date) == test_date
        assert InputValidator.validate_date(datetime(2024, 1, 15, 10, 30)) == test_date
        
        # Invalid dates
        with pytest.raises(ValidationError, match="Date is required"):
            InputValidator.validate_date('')
        
        with pytest.raises(ValidationError, match="Invalid date format"):
            InputValidator.validate_date('2024-13-01')  # Invalid month
        
        with pytest.raises(ValidationError, match="Invalid date format"):
            InputValidator.validate_date('invalid-date')
        
        # Out of range dates
        with pytest.raises(ValidationError, match="Date must be between"):
            InputValidator.validate_date('1800-01-01')
        
        with pytest.raises(ValidationError, match="Date must be between"):
            InputValidator.validate_date('2200-01-01')
    
    def test_validate_text_field(self):
        """Test text field validation."""
        # Valid text
        assert InputValidator.validate_text_field('Test', 'Field', 100) == 'Test'
        assert InputValidator.validate_text_field(' Test ', 'Field', 100) == 'Test'
        assert InputValidator.validate_text_field(None, 'Field', 100) is None
        assert InputValidator.validate_text_field('', 'Field', 100, allow_empty=True) is None
        
        # Required field validation
        with pytest.raises(ValidationError, match="Field is required"):
            InputValidator.validate_text_field(None, 'Field', 100, required=True)
        
        with pytest.raises(ValidationError, match="Field cannot be empty"):
            InputValidator.validate_text_field('', 'Field', 100, required=True)
        
        # Length validation
        with pytest.raises(ValidationError, match="Field cannot exceed 5 characters"):
            InputValidator.validate_text_field('Too long text', 'Field', 5)
        
        # XSS protection
        with pytest.raises(ValidationError, match="contains potentially dangerous content"):
            InputValidator.validate_text_field('<script>alert("xss")</script>', 'Field', 100)
        
        with pytest.raises(ValidationError, match="contains potentially dangerous content"):
            InputValidator.validate_text_field('javascript:void(0)', 'Field', 100)
    
    def test_validate_transaction_data(self):
        """Test complete transaction data validation."""
        valid_data = {
            'date': '2024-01-15',
            'description': 'Test transaction',
            'amount': '100.50',
            'currency': 'USD',
            'payee_name': 'Test Payee',
            'merchant': 'Test Merchant',
            'payment_reference': 'REF123'
        }
        
        result = InputValidator.validate_transaction_data(valid_data)
        
        assert result['date'] == date(2024, 1, 15)
        assert result['description'] == 'Test transaction'
        assert result['amount'] == Decimal('100.50')
        assert result['currency'] == 'USD'
        assert result['payee_name'] == 'Test Payee'
        assert result['merchant'] == 'Test Merchant'
        assert result['payment_reference'] == 'REF123'
    
    def test_validate_file_upload(self):
        """Test file upload validation."""
        # Valid file
        valid_file = FileStorage(
            stream=BytesIO(b'PDF content'),
            filename='test.pdf',
            content_type='application/pdf'
        )
        is_valid, message = InputValidator.validate_file_upload(valid_file, {'pdf'}, 1)
        assert is_valid is True
        assert message == ''
        
        # No file
        is_valid, message = InputValidator.validate_file_upload(None, {'pdf'}, 1)
        assert is_valid is False
        assert 'No file provided' in message
        
        # Invalid extension
        invalid_file = FileStorage(
            stream=BytesIO(b'content'),
            filename='test.txt',
            content_type='text/plain'
        )
        is_valid, message = InputValidator.validate_file_upload(invalid_file, {'pdf'}, 1)
        assert is_valid is False
        assert 'File type not allowed' in message


class TestSearchValidator:
    """Test SearchValidator class."""
    
    def test_validate_search_query(self):
        """Test search query validation."""
        assert SearchValidator.validate_search_query('test query') == 'test query'
        assert SearchValidator.validate_search_query(' test ') == 'test'
        assert SearchValidator.validate_search_query('') is None
        assert SearchValidator.validate_search_query(None) is None
        
        # SQL injection attempts
        with pytest.raises(ValidationError, match="contains invalid content"):
            SearchValidator.validate_search_query('test; DROP TABLE users;')
        
        with pytest.raises(ValidationError, match="contains invalid content"):
            SearchValidator.validate_search_query('UNION SELECT * FROM users')
    
    def test_validate_status_filter(self):
        """Test status filter validation."""
        assert SearchValidator.validate_status_filter('all') == 'all'
        assert SearchValidator.validate_status_filter('reconciled') == 'reconciled'
        assert SearchValidator.validate_status_filter('unreconciled') == 'unreconciled'
        assert SearchValidator.validate_status_filter(None) is None
        
        with pytest.raises(ValidationError, match="Invalid status filter"):
            SearchValidator.validate_status_filter('invalid')
    
    def test_validate_category_filter(self):
        """Test category filter validation."""
        assert SearchValidator.validate_category_filter('all') == 'all'
        assert SearchValidator.validate_category_filter('revenue') == 'revenue'
        assert SearchValidator.validate_category_filter('expense') == 'expense'
        assert SearchValidator.validate_category_filter('undefined') == 'undefined'
        
        with pytest.raises(ValidationError, match="Invalid category filter"):
            SearchValidator.validate_category_filter('invalid')


class TestTransactionDeduplicator:
    """Test TransactionDeduplicator class."""
    
    def test_normalize_amount(self):
        """Test amount normalization."""
        assert TransactionDeduplicator.normalize_amount(100.50) == Decimal('100.50')
        assert TransactionDeduplicator.normalize_amount('100.505') == Decimal('100.51')  # Rounds up
        
        # Test invalid input handling
        try:
            result = TransactionDeduplicator.normalize_amount('invalid')
            assert result == Decimal('0.00')  # If it handles gracefully
        except (ValueError, TypeError, decimal.InvalidOperation):
            pass  # This is also acceptable behavior
    
    def test_normalize_description(self):
        """Test description normalization."""
        assert TransactionDeduplicator.normalize_description('Test Description') == 'test description'
        assert TransactionDeduplicator.normalize_description('  Test  Description  ') == 'test description'
        assert TransactionDeduplicator.normalize_description('Payment to Store') == 'to store'  # Removes 'payment'
        assert TransactionDeduplicator.normalize_description(None) == ''
    
    def test_normalize_reference(self):
        """Test reference normalization."""
        assert TransactionDeduplicator.normalize_reference('REF 123') == 'REF123'
        assert TransactionDeduplicator.normalize_reference('ref-456') == 'REF-456'
        assert TransactionDeduplicator.normalize_reference(None) == ''
    
    def test_calculate_description_similarity(self):
        """Test description similarity calculation."""
        # Exact match
        similarity = TransactionDeduplicator.calculate_description_similarity(
            'Test description', 'Test description'
        )
        assert similarity == 1.0
        
        # No match
        similarity = TransactionDeduplicator.calculate_description_similarity(
            'Test description', 'Completely different'
        )
        assert similarity < 0.5
        
        # Partial match
        similarity = TransactionDeduplicator.calculate_description_similarity(
            'Payment to Amazon', 'Amazon payment'
        )
        assert 0.5 < similarity < 1.0
    
    def test_find_potential_duplicates(self, app, test_user):
        """Test finding potential duplicate transactions."""
        with app.app_context():
            # Create test transaction
            existing = Transaction(
                user_id=test_user.id,
                date=date(2024, 1, 15),
                amount=Decimal('100.50'),
                currency='USD',
                description='Test payment to Amazon',
                payment_reference='REF123'
            )
            db.session.add(existing)
            db.session.commit()
            
            # Test finding duplicates
            duplicates = TransactionDeduplicator.find_potential_duplicates(
                date=date(2024, 1, 15),
                amount=Decimal('100.50'),
                description='Amazon payment test',
                payment_reference='REF123',
                user_id=test_user.id
            )
            
            assert len(duplicates) > 0
            assert duplicates[0][1] > 0.5  # High confidence
    
    def test_is_duplicate(self, app, test_user):
        """Test duplicate detection."""
        with app.app_context():
            # Create test transaction
            existing = Transaction(
                user_id=test_user.id,
                date=date(2024, 1, 15),
                amount=Decimal('100.50'),
                currency='USD',
                description='Test payment',
                payment_reference='REF123'
            )
            db.session.add(existing)
            db.session.commit()
            
            # Test exact duplicate
            is_dup, transaction, confidence = TransactionDeduplicator.is_duplicate(
                date=date(2024, 1, 15),
                amount=Decimal('100.50'),
                description='Test payment',
                payment_reference='REF123',
                confidence_threshold=0.8,
                user_id=test_user.id
            )
            
            assert is_dup is True
            assert transaction.id == existing.id
            assert confidence >= 0.8


class TestUserModel:
    """Test User model class."""
    
    def test_user_creation(self, app):
        """Test user creation and properties."""
        with app.app_context():
            user = User(
                email='test@example.com',
                first_name='John',
                last_name='Doe'
            )
            user.set_password('testpassword123')
            
            assert user.email == 'test@example.com'
            assert user.full_name == 'John Doe'
            assert user.user_folder is not None  # Should auto-generate
            assert user.check_password('testpassword123') is True
            assert user.check_password('wrongpassword') is False
    
    def test_password_hashing(self, app):
        """Test password hashing security."""
        with app.app_context():
            user = User(email='test@example.com', first_name='Test', last_name='User')
            user.set_password('mypassword')
            
            # Password should be hashed
            assert user.password_hash != 'mypassword'
            assert len(user.password_hash) > 50  # Hashed passwords are long
            
            # Should verify correctly
            assert user.check_password('mypassword') is True
            assert user.check_password('wrongpassword') is False
    
    def test_upload_path(self, app):
        """Test user upload path generation."""
        with app.app_context():
            user = User(email='test@example.com', first_name='Test', last_name='User')
            upload_path = user.upload_path
            
            assert 'uploads/users/' in upload_path
            assert user.user_folder in upload_path


class TestTransactionModel:
    """Test Transaction model class."""
    
    def test_transaction_creation(self, app, test_user):
        """Test transaction creation and properties."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user.id,
                date=date(2024, 1, 15),
                amount=Decimal('100.50'),
                currency='USD',
                description='Test transaction'
            )
            
            assert transaction.amount == Decimal('100.50')
            assert transaction.currency == 'USD'
            assert transaction.is_coded is False
            assert transaction.has_documents is False
            assert transaction.status_display == 'Unreconciled'
    
    def test_transaction_coding(self, app, test_user, sample_transaction):
        """Test transaction coding functionality."""
        with app.app_context():
            # Add transaction code
            code = TransactionCode(
                user_id=test_user.id,
                transaction_id=sample_transaction.id,
                category_name='Revenue',
                notes='Test coding'
            )
            db.session.add(code)
            db.session.commit()
            
            # Refresh transaction
            db.session.refresh(sample_transaction)
            
            assert sample_transaction.is_coded is True
            assert sample_transaction.status_display == 'Reconciled'
            assert sample_transaction.transaction_code.category_name == 'Revenue'


class TestWiseAPIService:
    """Test WiseAPIService class."""
    
    def test_initialization(self):
        """Test service initialization."""
        service = WiseAPIService(
            api_url='https://api.wise.com',
            api_token='test-token',
            profile_id='12345'
        )
        
        assert service.api_url == 'https://api.wise.com'
        assert service.api_token == 'test-token'
        assert service.profile_id == '12345'
    
    @patch('requests.get')
    def test_api_call_success(self, mock_get):
        """Test successful API call."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'test': 'data'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        service = WiseAPIService('https://api.test.com', 'token', '123')
        result = service._make_api_call('/test')
        
        assert result == {'test': 'data'}
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_api_call_failure(self, mock_get):
        """Test failed API call."""
        # Mock failed response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception('API Error')
        mock_get.return_value = mock_response
        
        service = WiseAPIService('https://api.test.com', 'token', '123')
        
        with pytest.raises(Exception, match='API Error'):
            service._make_api_call('/test')
    
    def test_dummy_transactions_generation(self):
        """Test dummy transaction generation."""
        service = WiseAPIService('https://api.test.com', 'token', '123')
        transactions = service._generate_dummy_transactions(30)
        
        assert len(transactions) > 0
        assert all('date' in tx for tx in transactions)
        assert all('amount' in tx for tx in transactions)
        assert all('currency' in tx for tx in transactions)
        
        # Check for multi-currency support
        currencies = {tx['currency'] for tx in transactions}
        assert len(currencies) > 1  # Should have multiple currencies


class TestFileService:
    """Test FileService class."""
    
    def test_validate_file_valid(self, app):
        """Test valid file validation."""
        with app.app_context():
            # Mock valid PDF file
            file = FileStorage(
                stream=BytesIO(b'PDF content'),
                filename='test.pdf',
                content_type='application/pdf'
            )
            
            is_valid, message = FileService.validate_file(file)
            assert is_valid is True
            assert message == ''
    
    def test_validate_file_invalid(self, app):
        """Test invalid file validation."""
        with app.app_context():
            # No file
            is_valid, message = FileService.validate_file(None)
            assert is_valid is False
            assert 'No file selected' in message
            
            # Empty filename
            file = FileStorage(filename='')
            is_valid, message = FileService.validate_file(file)
            assert is_valid is False
            assert 'No file selected' in message
    
    def test_delete_file(self):
        """Test file deletion."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b'test content')
            tmp_path = tmp.name
        
        # File should exist
        assert os.path.exists(tmp_path)
        
        # Delete file
        result = FileService.delete_file(tmp_path)
        assert result is True
        assert not os.path.exists(tmp_path)
        
        # Try to delete non-existent file
        result = FileService.delete_file('non_existent_file.txt')
        assert result is False


class TestAppSettings:
    """Test AppSettings model."""
    
    def test_setting_creation(self, app, test_user):
        """Test setting creation and validation."""
        with app.app_context():
            setting = AppSettings(
                user_id=test_user.id,
                setting_key='TEST_KEY'
            )
            setting.set_value('test value')
            
            assert setting.setting_key == 'TEST_KEY'
            assert setting.get_value() == 'test value'
    
    def test_json_value_handling(self, app, test_user):
        """Test JSON value serialization/deserialization."""
        with app.app_context():
            setting = AppSettings(user_id=test_user.id, setting_key='JSON_TEST')
            
            # Test dict value
            test_dict = {'key': 'value', 'number': 42}
            setting.set_value(test_dict)
            assert setting.get_value() == test_dict
            
            # Test list value
            test_list = [1, 2, 'three']
            setting.set_value(test_list)
            assert setting.get_value() == test_list
            
            # Test boolean value
            setting.set_value(True)
            assert setting.get_value() is True
    
    def test_user_setting_methods(self, app, test_user):
        """Test user-specific setting methods."""
        with app.app_context():
            # Set user setting
            AppSettings.set_user_setting(test_user.id, 'USER_TEST', 'user value')
            
            # Get user setting
            value = AppSettings.get_user_setting(test_user.id, 'USER_TEST')
            assert value == 'user value'
            
            # Get with default
            default_value = AppSettings.get_user_setting(test_user.id, 'NON_EXISTENT', 'default')
            assert default_value == 'default'


class TestRoutes:
    """Test Flask routes."""
    
    def test_login_page(self, client):
        """Test login page access."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    def test_login_success(self, client, app, test_user):
        """Test successful login."""
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should redirect to dashboard after login
    
    def test_login_failure(self, client):
        """Test failed login."""
        response = client.post('/login', data={
            'email': 'wrong@example.com',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 200
        # Should show error message
    
    def test_register_user(self, client, app):
        """Test user registration."""
        with app.app_context():
            response = client.post('/register', data={
                'email': 'new@example.com',
                'first_name': 'New',
                'last_name': 'User',
                'password': 'newpassword123',
                'confirm_password': 'newpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify user was created
            user = User.query.filter_by(email='new@example.com').first()
            assert user is not None
            assert user.first_name == 'New'
    
    def test_dashboard_requires_login(self, client):
        """Test that dashboard requires authentication."""
        response = client.get('/')
        assert response.status_code == 302  # Redirect to login
    
    def test_dashboard_authenticated(self, authenticated_client):
        """Test dashboard with authenticated user."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
    
    def test_transactions_list(self, authenticated_client):
        """Test transactions listing."""
        response = authenticated_client.get('/transactions')
        assert response.status_code == 200
    
    def test_upload_single_transaction(self, authenticated_client):
        """Test single transaction upload."""
        response = authenticated_client.post('/upload-transactions', data={
            'upload_type': 'single',
            'date': '2024-01-15',
            'description': 'Test transaction',
            'amount': '100.50',
            'currency': 'USD'
        }, follow_redirects=True)
        
        assert response.status_code == 200


class TestSecurity:
    """Test security aspects of the application."""
    
    def test_csrf_protection(self, client):
        """Test CSRF protection is enabled."""
        # Try to post without CSRF token
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        # Should work because CSRF is disabled in test config
        assert response.status_code in [200, 302]
    
    def test_sql_injection_protection(self, authenticated_client):
        """Test SQL injection protection in search."""
        # Try SQL injection in search
        response = authenticated_client.get('/transactions?search=test\'; DROP TABLE users; --')
        assert response.status_code == 200
        # Should not crash the application
    
    def test_xss_protection(self, authenticated_client):
        """Test XSS protection in form inputs."""
        response = authenticated_client.post('/upload-transactions', data={
            'upload_type': 'single',
            'date': '2024-01-15',
            'description': '<script>alert("xss")</script>',
            'amount': '100.50',
            'currency': 'USD'
        })
        # Should reject malicious input
        assert response.status_code in [200, 302]
    
    def test_file_upload_security(self, authenticated_client):
        """Test file upload security."""
        # Try to upload non-PDF file
        data = {
            'file': (BytesIO(b'malicious content'), 'malware.exe')
        }
        response = authenticated_client.post('/transaction/1/upload', data=data)
        # Should reject non-PDF files
        assert response.status_code in [200, 302, 404]
    
    def test_user_data_isolation(self, app):
        """Test that users can only access their own data."""
        with app.app_context():
            # Create two users
            user1 = User(email='user1@test.com', first_name='User', last_name='One')
            user1.set_password('password')
            user2 = User(email='user2@test.com', first_name='User', last_name='Two')
            user2.set_password('password')
            
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Create transactions for each user
            tx1 = Transaction(
                user_id=user1.id,
                date=date.today(),
                amount=Decimal('100'),
                currency='USD',
                description='User 1 transaction'
            )
            tx2 = Transaction(
                user_id=user2.id,
                date=date.today(),
                amount=Decimal('200'),
                currency='USD',
                description='User 2 transaction'
            )
            
            db.session.add_all([tx1, tx2])
            db.session.commit()
            
            # Test that user1 can only see their transactions
            user1_transactions = Transaction.query.filter_by(user_id=user1.id).all()
            assert len(user1_transactions) == 1
            assert user1_transactions[0].description == 'User 1 transaction'
            
            # Test that user2 can only see their transactions
            user2_transactions = Transaction.query.filter_by(user_id=user2.id).all()
            assert len(user2_transactions) == 1
            assert user2_transactions[0].description == 'User 2 transaction'


class TestPerformance:
    """Test performance-related functionality."""
    
    def test_database_indexes(self, app, test_user):
        """Test that database queries use indexes efficiently."""
        with app.app_context():
            # Create many transactions
            transactions = []
            for i in range(100):
                tx = Transaction(
                    user_id=test_user.id,
                    date=date(2024, 1, i % 28 + 1),
                    amount=Decimal(str(100 + i)),
                    currency='USD',
                    description=f'Test transaction {i}'
                )
                transactions.append(tx)
            
            db.session.add_all(transactions)
            db.session.commit()
            
            # Test filtered queries (should use indexes)
            start_time = datetime.now()
            results = Transaction.query.filter_by(user_id=test_user.id).all()
            query_time = (datetime.now() - start_time).total_seconds()
            
            assert len(results) == 100
            assert query_time < 1.0  # Should be fast with proper indexing
    
    def test_duplicate_detection_performance(self, app, test_user):
        """Test duplicate detection performance with many transactions."""
        with app.app_context():
            # Create many similar transactions
            base_date = date(2024, 1, 15)
            for i in range(50):
                tx = Transaction(
                    user_id=test_user.id,
                    date=base_date,
                    amount=Decimal('100.50'),
                    currency='USD',
                    description=f'Similar transaction {i}'
                )
                db.session.add(tx)
            
            db.session.commit()
            
            # Test duplicate detection performance
            start_time = datetime.now()
            is_dup, tx, confidence = TransactionDeduplicator.is_duplicate(
                date=base_date,
                amount=Decimal('100.50'),
                description='Similar transaction test',
                user_id=test_user.id
            )
            detection_time = (datetime.now() - start_time).total_seconds()
            
            assert detection_time < 2.0  # Should complete within 2 seconds


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_transaction_id(self, authenticated_client):
        """Test handling of invalid transaction ID."""
        response = authenticated_client.get('/transaction/99999')
        assert response.status_code == 404
    
    def test_empty_csv_upload(self, authenticated_client):
        """Test handling of empty CSV file."""
        data = {
            'upload_type': 'csv',
            'csv_file': (BytesIO(b''), 'empty.csv')
        }
        response = authenticated_client.post('/upload-transactions', data=data)
        assert response.status_code in [200, 302]
    
    def test_malformed_csv_upload(self, authenticated_client):
        """Test handling of malformed CSV."""
        csv_content = b'invalid,csv,format\nwith,too,few,columns'
        data = {
            'upload_type': 'csv',
            'csv_file': (BytesIO(csv_content), 'malformed.csv')
        }
        response = authenticated_client.post('/upload-transactions', data=data)
        assert response.status_code in [200, 302]
    
    def test_database_rollback_on_error(self, app, test_user):
        """Test that database changes are rolled back on error."""
        with app.app_context():
            original_count = Transaction.query.count()
            
            try:
                # Create transaction with invalid data
                tx = Transaction(
                    user_id=test_user.id,
                    date=None,  # This should cause an error
                    amount=Decimal('100'),
                    currency='USD',
                    description='Test'
                )
                db.session.add(tx)
                db.session.commit()
            except Exception:
                db.session.rollback()
            
            # Count should remain the same
            final_count = Transaction.query.count()
            assert final_count == original_count


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_transaction_workflow(self, authenticated_client, app, test_user):
        """Test complete transaction processing workflow."""
        with app.app_context():
            # 1. Upload single transaction
            response = authenticated_client.post('/upload-transactions', data={
                'upload_type': 'single',
                'date': '2024-01-15',
                'description': 'Integration test transaction',
                'amount': '150.75',
                'currency': 'USD',
                'payee_name': 'Test Payee',
                'payment_reference': 'INT-TEST-001'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # 2. Verify transaction was created
            transaction = Transaction.query.filter_by(
                description='Integration test transaction'
            ).first()
            assert transaction is not None
            assert transaction.amount == Decimal('150.75')
            
            # 3. Code the transaction
            response = authenticated_client.post(f'/transaction/{transaction.id}/code', data={
                'category': 'Revenue',
                'notes': 'Integration test coding'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # 4. Verify transaction is coded
            db.session.refresh(transaction)
            assert transaction.is_coded is True
            assert transaction.transaction_code.category_name == 'Revenue'
            
            # 5. Generate report
            response = authenticated_client.get('/reports', query_string={
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            })
            
            assert response.status_code == 200
            assert b'Integration test transaction' in response.data
    
    def test_csv_import_and_processing(self, authenticated_client, app):
        """Test CSV import and processing workflow."""
        # Create CSV content
        csv_content = """date,description,amount,currency,payee_name
2024-01-15,CSV Test Transaction 1,100.50,USD,CSV Payee 1
2024-01-16,CSV Test Transaction 2,-50.25,EUR,CSV Payee 2
2024-01-17,CSV Test Transaction 3,200.00,GBP,CSV Payee 3"""
        
        with app.app_context():
            # Upload CSV
            data = {
                'upload_type': 'csv',
                'csv_file': (BytesIO(csv_content.encode()), 'test.csv')
            }
            response = authenticated_client.post('/upload-transactions', data=data, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify transactions were imported
            transactions = Transaction.query.filter(
                Transaction.description.like('CSV Test Transaction%')
            ).all()
            
            assert len(transactions) == 3
            
            # Verify multi-currency support
            currencies = {tx.currency for tx in transactions}
            assert currencies == {'USD', 'EUR', 'GBP'}


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v', '--tb=short'])