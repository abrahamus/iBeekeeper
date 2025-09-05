"""
Transaction deduplication utilities for robust duplicate detection across import methods.
"""
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from models import Transaction, db
import re


class TransactionDeduplicator:
    """
    Handles robust duplicate detection for transactions across all import methods.
    Uses multiple strategies to identify potential duplicates.
    """
    
    # Thresholds for fuzzy matching
    DESCRIPTION_SIMILARITY_THRESHOLD = 0.85
    AMOUNT_TOLERANCE = Decimal('0.01')  # 1 cent tolerance
    
    @staticmethod
    def normalize_amount(amount_value):
        """
        Normalize amount to 2 decimal places to handle floating point precision issues.
        
        Args:
            amount_value: float, int, str, or Decimal amount
            
        Returns:
            Decimal: Normalized amount with 2 decimal places
        """
        try:
            decimal_amount = Decimal(str(amount_value))
            return decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (ValueError, TypeError):
            return Decimal('0.00')
    
    @staticmethod
    def normalize_description(description):
        """
        Normalize description for comparison - case insensitive, remove extra spaces.
        
        Args:
            description (str): Transaction description
            
        Returns:
            str: Normalized description
        """
        if not description:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = ' '.join(description.lower().strip().split())
        
        # Remove common banking suffixes/prefixes that might vary
        patterns_to_remove = [
            r'\b(payment|transfer|debit|credit)\b',
            r'\b(ref\s*:?\s*\w+)\b',
            r'\b(transaction\s*id\s*:?\s*\w+)\b'
        ]
        
        for pattern in patterns_to_remove:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        return ' '.join(normalized.split())  # Remove extra spaces after removal
    
    @staticmethod
    def normalize_reference(reference):
        """
        Normalize payment reference for comparison.
        
        Args:
            reference (str): Payment reference
            
        Returns:
            str: Normalized reference (uppercase, no spaces)
        """
        if not reference:
            return ""
        return re.sub(r'\s+', '', reference.upper())
    
    @staticmethod
    def calculate_description_similarity(desc1, desc2):
        """
        Calculate similarity between two descriptions using difflib.
        
        Args:
            desc1 (str): First description
            desc2 (str): Second description
            
        Returns:
            float: Similarity ratio (0.0 to 1.0)
        """
        if not desc1 or not desc2:
            return 0.0
            
        norm1 = TransactionDeduplicator.normalize_description(desc1)
        norm2 = TransactionDeduplicator.normalize_description(desc2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @classmethod
    def find_potential_duplicates(cls, date, amount, description, payment_reference=None, 
                                 payee_name=None, exclude_id=None, user_id=None):
        """
        Find potential duplicate transactions using multiple criteria.
        
        Args:
            date: Transaction date
            amount: Transaction amount
            description: Transaction description  
            payment_reference: Optional payment reference
            payee_name: Optional payee name
            exclude_id: Optional transaction ID to exclude from results
            user_id: Optional user ID to filter by (for multi-user support)
            
        Returns:
            list: List of (transaction, confidence_score) tuples, ordered by confidence
        """
        normalized_amount = cls.normalize_amount(amount)
        normalized_desc = cls.normalize_description(description)
        normalized_ref = cls.normalize_reference(payment_reference)
        
        # Build optimized query for potential duplicates
        # Add amount range filter to reduce candidates before Python-level comparison
        amount_tolerance = normalized_amount * Decimal('0.05')  # 5% tolerance for amounts
        min_amount = normalized_amount - amount_tolerance
        max_amount = normalized_amount + amount_tolerance
        
        query = Transaction.query.filter(
            Transaction.date == date,
            Transaction.amount.between(min_amount, max_amount)
        )
        
        # Filter by user if provided (multi-user support)
        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        
        if exclude_id:
            query = query.filter(Transaction.id != exclude_id)
        
        # Limit to recent transactions to avoid scanning entire history
        candidates = query.order_by(Transaction.created_at.desc()).limit(20).all()
        potential_duplicates = []
        
        for candidate in candidates:
            confidence_score = cls._calculate_duplicate_confidence(
                candidate, normalized_amount, normalized_desc, normalized_ref, payee_name
            )
            
            if confidence_score > 0.5:  # Only consider matches above 50% confidence
                potential_duplicates.append((candidate, confidence_score))
        
        # Sort by confidence score (highest first)
        potential_duplicates.sort(key=lambda x: x[1], reverse=True)
        
        return potential_duplicates
    
    @classmethod
    def _calculate_duplicate_confidence(cls, candidate, normalized_amount, normalized_desc, 
                                      normalized_ref, payee_name):
        """
        Calculate confidence score that a candidate transaction is a duplicate.
        
        Returns:
            float: Confidence score (0.0 to 1.0)
        """
        confidence = 0.0
        
        # Amount matching (40% weight)
        candidate_amount = cls.normalize_amount(candidate.amount)
        amount_diff = abs(normalized_amount - candidate_amount)
        
        if amount_diff == 0:
            confidence += 0.4  # Exact match
        elif amount_diff <= cls.AMOUNT_TOLERANCE:
            confidence += 0.3  # Close match
        else:
            confidence += max(0, 0.2 - float(amount_diff))  # Partial credit for small differences
        
        # Description matching (35% weight)
        if candidate.description:
            desc_similarity = cls.calculate_description_similarity(
                candidate.description, normalized_desc
            )
            if desc_similarity >= cls.DESCRIPTION_SIMILARITY_THRESHOLD:
                confidence += 0.35
            else:
                confidence += desc_similarity * 0.25  # Partial credit
        
        # Payment reference matching (15% weight)
        if normalized_ref and candidate.payment_reference:
            candidate_ref = cls.normalize_reference(candidate.payment_reference)
            if candidate_ref == normalized_ref:
                confidence += 0.15
            elif normalized_ref in candidate_ref or candidate_ref in normalized_ref:
                confidence += 0.1  # Partial match
        
        # Payee name matching (10% weight)  
        if payee_name and candidate.payee_name:
            payee_similarity = SequenceMatcher(
                None, 
                payee_name.lower().strip(), 
                candidate.payee_name.lower().strip()
            ).ratio()
            confidence += payee_similarity * 0.1
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    @classmethod
    def is_duplicate(cls, date, amount, description, payment_reference=None, 
                    payee_name=None, exclude_id=None, confidence_threshold=0.8, user_id=None):
        """
        Check if a transaction is likely a duplicate.
        
        Args:
            date: Transaction date
            amount: Transaction amount
            description: Transaction description
            payment_reference: Optional payment reference
            payee_name: Optional payee name
            exclude_id: Optional transaction ID to exclude
            confidence_threshold: Minimum confidence to consider duplicate (default 0.8)
            user_id: Optional user ID to filter by (for multi-user support)
            
        Returns:
            tuple: (is_duplicate: bool, existing_transaction: Transaction or None, confidence: float)
        """
        potential_duplicates = cls.find_potential_duplicates(
            date, amount, description, payment_reference, payee_name, exclude_id, user_id
        )
        
        if potential_duplicates and potential_duplicates[0][1] >= confidence_threshold:
            return True, potential_duplicates[0][0], potential_duplicates[0][1]
        
        return False, None, 0.0
    
    @classmethod
    def get_exact_match(cls, date, amount, description, user_id=None):
        """
        Get exact match using the legacy logic (for backwards compatibility).
        
        Args:
            date: Transaction date
            amount: Transaction amount  
            description: Transaction description
            user_id: Optional user ID to filter by (for multi-user support)
        
        Returns:
            Transaction or None
        """
        normalized_amount = cls.normalize_amount(amount)
        normalized_desc = cls.normalize_description(description)
        
        # Try to find exact matches
        query = Transaction.query.filter(Transaction.date == date)
        
        # Filter by user if provided (multi-user support)
        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        
        candidates = query.all()
        
        for candidate in candidates:
            candidate_amount = cls.normalize_amount(candidate.amount)
            candidate_desc = cls.normalize_description(candidate.description)
            
            if (candidate_amount == normalized_amount and 
                candidate_desc == normalized_desc):
                return candidate
        
        return None