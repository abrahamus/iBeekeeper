"""
Input validation utilities for the bookkeeping application.
Provides comprehensive validation for financial data and user inputs.
"""

import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, Union


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class InputValidator:
    """Comprehensive input validation for bookkeeping data"""
    
    # Currency codes (ISO 4217 standard - common subset)
    VALID_CURRENCIES = {
        'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'SEK', 'NOK', 'DKK',
        'PLN', 'CZK', 'HUF', 'BGN', 'RON', 'HRK', 'RUB', 'TRY', 'BRL', 'MXN',
        'CNY', 'INR', 'KRW', 'SGD', 'HKD', 'TWD', 'THB', 'MYR', 'IDR', 'PHP',
        'VND', 'ZAR', 'NZD', 'ILS', 'AED', 'SAR', 'QAR', 'KWD', 'BHD', 'OMR'
    }
    
    # Maximum field lengths
    MAX_DESCRIPTION_LENGTH = 500
    MAX_PAYEE_NAME_LENGTH = 200
    MAX_MERCHANT_LENGTH = 200
    MAX_PAYMENT_REFERENCE_LENGTH = 100
    MAX_NOTES_LENGTH = 1000
    
    # Amount limits (in absolute value)
    MIN_AMOUNT = Decimal('0.01')
    MAX_AMOUNT = Decimal('999999999.99')
    
    @staticmethod
    def validate_amount(amount: Union[str, int, float, Decimal]) -> Decimal:
        """
        Validate and convert amount to Decimal for precise currency calculations.
        
        Args:
            amount: Amount to validate (string, int, float, or Decimal)
            
        Returns:
            Decimal: Validated amount
            
        Raises:
            ValidationError: If amount is invalid
        """
        try:
            if isinstance(amount, str):
                amount = amount.strip()
                if not amount:
                    raise ValidationError("Amount cannot be empty")
            
            decimal_amount = Decimal(str(amount))
            
            # Check for reasonable bounds
            if abs(decimal_amount) < InputValidator.MIN_AMOUNT and decimal_amount != 0:
                raise ValidationError(f"Amount must be at least {InputValidator.MIN_AMOUNT} or zero")
            
            if abs(decimal_amount) > InputValidator.MAX_AMOUNT:
                raise ValidationError(f"Amount cannot exceed {InputValidator.MAX_AMOUNT}")
            
            # Check for too many decimal places (max 2 for currency)
            if decimal_amount.as_tuple().exponent < -2:
                raise ValidationError("Amount cannot have more than 2 decimal places")
                
            return decimal_amount
            
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(f"Invalid amount format: {amount}")
    
    @staticmethod
    def validate_currency_code(currency: str) -> str:
        """
        Validate currency code against ISO 4217 standard.
        
        Args:
            currency: Currency code to validate
            
        Returns:
            str: Validated uppercase currency code
            
        Raises:
            ValidationError: If currency code is invalid
        """
        if not currency:
            raise ValidationError("Currency code is required")
        
        currency = currency.strip().upper()
        
        if len(currency) != 3:
            raise ValidationError("Currency code must be exactly 3 letters")
        
        if not currency.isalpha():
            raise ValidationError("Currency code must contain only letters")
        
        if currency not in InputValidator.VALID_CURRENCIES:
            raise ValidationError(f"Unsupported currency code: {currency}")
        
        return currency
    
    @staticmethod
    def validate_date(date_input: Union[str, date, datetime]) -> date:
        """
        Validate and convert date input.
        
        Args:
            date_input: Date to validate (string, date, or datetime)
            
        Returns:
            date: Validated date object
            
        Raises:
            ValidationError: If date is invalid
        """
        if isinstance(date_input, datetime):
            return date_input.date()
        
        if isinstance(date_input, date):
            return date_input
        
        if isinstance(date_input, str):
            date_input = date_input.strip()
            if not date_input:
                raise ValidationError("Date is required")
            
            # Try common date formats
            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_input, fmt).date()
                    
                    # Check for reasonable date bounds
                    min_date = date(1900, 1, 1)
                    max_date = date(2100, 12, 31)
                    
                    if parsed_date < min_date or parsed_date > max_date:
                        raise ValidationError(f"Date must be between {min_date} and {max_date}")
                    
                    return parsed_date
                except ValueError:
                    continue
            
            raise ValidationError(f"Invalid date format: {date_input}")
        
        raise ValidationError("Date must be a string, date, or datetime object")
    
    @staticmethod
    def validate_text_field(value: Optional[str], field_name: str, max_length: int, 
                           required: bool = False, allow_empty: bool = True) -> Optional[str]:
        """
        Validate text field with length and content checks.
        
        Args:
            value: Text value to validate
            field_name: Name of the field for error messages
            max_length: Maximum allowed length
            required: Whether the field is required
            allow_empty: Whether empty strings are allowed
            
        Returns:
            str or None: Validated text value
            
        Raises:
            ValidationError: If text is invalid
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")
        
        value = value.strip()
        
        if not value:
            if required or not allow_empty:
                raise ValidationError(f"{field_name} cannot be empty")
            return None
        
        if len(value) > max_length:
            raise ValidationError(f"{field_name} cannot exceed {max_length} characters")
        
        # Check for potentially dangerous content (basic XSS prevention)
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                raise ValidationError(f"{field_name} contains potentially dangerous content")
        
        return value
    
    @staticmethod
    def validate_description(description: str) -> str:
        """Validate transaction description"""
        return InputValidator.validate_text_field(
            description, "Description", InputValidator.MAX_DESCRIPTION_LENGTH, required=True
        )
    
    @staticmethod
    def validate_payee_name(payee_name: Optional[str]) -> Optional[str]:
        """Validate payee name"""
        return InputValidator.validate_text_field(
            payee_name, "Payee name", InputValidator.MAX_PAYEE_NAME_LENGTH
        )
    
    @staticmethod
    def validate_merchant(merchant: Optional[str]) -> Optional[str]:
        """Validate merchant name"""
        return InputValidator.validate_text_field(
            merchant, "Merchant", InputValidator.MAX_MERCHANT_LENGTH
        )
    
    @staticmethod
    def validate_payment_reference(payment_reference: Optional[str]) -> Optional[str]:
        """Validate payment reference"""
        return InputValidator.validate_text_field(
            payment_reference, "Payment reference", InputValidator.MAX_PAYMENT_REFERENCE_LENGTH
        )
    
    @staticmethod
    def validate_notes(notes: Optional[str]) -> Optional[str]:
        """Validate notes field"""
        return InputValidator.validate_text_field(
            notes, "Notes", InputValidator.MAX_NOTES_LENGTH
        )
    
    @staticmethod
    def validate_category(category: str) -> str:
        """
        Validate transaction category.
        
        Args:
            category: Category to validate
            
        Returns:
            str: Validated category
            
        Raises:
            ValidationError: If category is invalid
        """
        if not category:
            raise ValidationError("Category is required")
        
        category = category.strip()
        
        # Import here to avoid circular imports
        from config import Config
        
        if category not in Config.CATEGORIES:
            raise ValidationError(f"Invalid category. Must be one of: {', '.join(Config.CATEGORIES)}")
        
        return category
    
    @staticmethod
    def validate_transaction_data(data: dict) -> dict:
        """
        Validate complete transaction data.
        
        Args:
            data: Dictionary containing transaction data
            
        Returns:
            dict: Validated transaction data
            
        Raises:
            ValidationError: If any field is invalid
        """
        validated_data = {}
        
        # Required fields
        validated_data['date'] = InputValidator.validate_date(data.get('date'))
        validated_data['description'] = InputValidator.validate_description(data.get('description', ''))
        validated_data['amount'] = InputValidator.validate_amount(data.get('amount'))
        validated_data['currency'] = InputValidator.validate_currency_code(data.get('currency', 'USD'))
        
        # Optional fields
        validated_data['payee_name'] = InputValidator.validate_payee_name(data.get('payee_name'))
        validated_data['merchant'] = InputValidator.validate_merchant(data.get('merchant'))
        validated_data['payment_reference'] = InputValidator.validate_payment_reference(data.get('payment_reference'))
        
        return validated_data
    
    @staticmethod
    def validate_file_upload(file, allowed_extensions: set, max_size_mb: int = 16) -> Tuple[bool, str]:
        """
        Validate file upload.
        
        Args:
            file: Uploaded file object
            allowed_extensions: Set of allowed file extensions
            max_size_mb: Maximum file size in MB
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not file:
            return False, "No file provided"
        
        if not file.filename:
            return False, "No filename provided"
        
        # Check file extension
        if '.' not in file.filename:
            return False, "File must have an extension"
        
        extension = file.filename.rsplit('.', 1)[1].lower()
        if extension not in allowed_extensions:
            return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"File size exceeds {max_size_mb}MB limit"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, ""


class SearchValidator:
    """Validation for search and filter inputs"""
    
    MAX_SEARCH_LENGTH = 200
    
    @staticmethod
    def validate_search_query(query: Optional[str]) -> Optional[str]:
        """
        Validate search query input.
        
        Args:
            query: Search query to validate
            
        Returns:
            str or None: Validated search query
            
        Raises:
            ValidationError: If query is invalid
        """
        if not query:
            return None
        
        if not isinstance(query, str):
            raise ValidationError("Search query must be a string")
        
        query = query.strip()
        
        if not query:
            return None
        
        if len(query) > SearchValidator.MAX_SEARCH_LENGTH:
            raise ValidationError(f"Search query cannot exceed {SearchValidator.MAX_SEARCH_LENGTH} characters")
        
        # Basic SQL injection prevention
        dangerous_patterns = [
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            r'update\s+.+set',
            r'exec\s*\(',
            r'<script[^>]*>',
            r'javascript:'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValidationError("Search query contains invalid content")
        
        return query
    
    @staticmethod
    def validate_status_filter(status: Optional[str]) -> Optional[str]:
        """Validate status filter value"""
        if not status:
            return None
        
        valid_statuses = ['all', 'reconciled', 'unreconciled']
        
        if status not in valid_statuses:
            raise ValidationError(f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}")
        
        return status
    
    @staticmethod
    def validate_category_filter(category: Optional[str]) -> Optional[str]:
        """Validate category filter value"""
        if not category:
            return None
        
        valid_categories = ['all', 'revenue', 'expense', 'undefined']
        
        if category not in valid_categories:
            raise ValidationError(f"Invalid category filter. Must be one of: {', '.join(valid_categories)}")
        
        return category