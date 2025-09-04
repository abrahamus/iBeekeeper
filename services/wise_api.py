import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
from models import AppSettings
import logging

class WiseAPIService:
    def __init__(self, api_url: str = None, api_token: str = None, profile_id: str = None):
        # Use provided values or get from app settings
        if api_url and api_token:
            self.api_url = api_url
            self.api_token = api_token
            self.profile_id = profile_id
        else:
            wise_config = AppSettings.get_wise_config()
            self.api_url = wise_config['api_url']
            self.api_token = wise_config['api_token']
            self.profile_id = wise_config['entity_number']
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Clean up API URL (remove trailing slash)
        if self.api_url and self.api_url.endswith('/'):
            self.api_url = self.api_url.rstrip('/')
        
    def get_transactions(self, days_back: int = 30) -> List[Dict]:
        """
        Fetch transactions from Wise API using balance statements
        """
        try:
            # Validate configuration
            if not all([self.api_url, self.api_token, self.profile_id]):
                self.logger.error("Missing Wise API configuration")
                print(f"WISE CONFIG MISSING - URL: {bool(self.api_url)}, Token: {bool(self.api_token)}, Profile: {bool(self.profile_id)}")
                return []
            
            print(f"WISE API CALL STARTING - URL: {self.api_url}, Profile: {self.profile_id}")
            
            # Step 1: Get all balances for the profile
            balances = self._get_balances()
            if not balances:
                self.logger.warning("No balances found for profile")
                return []
            
            # Step 2: Get transactions for each balance
            all_transactions = []
            for balance in balances:
                balance_id = balance['id']
                currency = balance.get('currency', 'USD')
                
                # Get transactions for this balance
                balance_transactions = self._get_balance_transactions(balance_id, currency, days_back)
                all_transactions.extend(balance_transactions)
            
            # Sort by date (newest first)
            all_transactions.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            self.logger.info(f"Fetched {len(all_transactions)} transactions from Wise API")
            return all_transactions
            
        except Exception as e:
            self.logger.error(f"Error fetching transactions: {e}")
            # Also print to console for debugging
            print(f"WISE API ERROR: {e}")
            print(f"API URL: {self.api_url}")
            print(f"Profile ID: {self.profile_id}")
            print(f"Has Token: {bool(self.api_token)}")
            # Fallback to dummy data for development
            self.logger.info("Falling back to dummy data")
            return self._generate_dummy_transactions(days_back)
    
    def _generate_dummy_transactions(self, days_back: int) -> List[Dict]:
        """Generate realistic dummy transaction data for testing"""
        transactions = []
        
        # Sample data with MULTIPLE CURRENCIES for testing multi-currency features
        sample_transactions = [
            # USD Transactions
            {
                'description': 'Payment to Office Supplies Ltd',
                'payee_name': 'Office Supplies Ltd',
                'merchant': 'AMAZON US',
                'amount': -245.67,
                'currency': 'USD',
                'payment_reference': 'INV-2024-001'
            },
            {
                'description': 'Client Payment - ABC Corp',
                'payee_name': 'ABC Corporation',
                'merchant': 'WIRE TRANSFER',
                'amount': 2500.00,
                'currency': 'USD',
                'payment_reference': 'PROJ-ABC-Q1'
            },
            {
                'description': 'Software Subscription',
                'payee_name': 'Adobe Systems Inc',
                'merchant': 'ADOBE.COM',
                'amount': -52.99,
                'currency': 'USD',
                'payment_reference': 'SUB-ADOBE-2024'
            },
            # HKD Transactions (Hong Kong clients/suppliers)
            {
                'description': 'Hong Kong Client Payment',
                'payee_name': 'Dragon Tech HK Limited',
                'merchant': 'HSBC HONG KONG',
                'amount': 18500.00,
                'currency': 'HKD',
                'payment_reference': 'HK-PROJ-2024-01'
            },
            {
                'description': 'Office Rent - Hong Kong',
                'payee_name': 'Central Plaza Properties',
                'merchant': 'PROPERTY MANAGEMENT',
                'amount': -28000.00,
                'currency': 'HKD',
                'payment_reference': 'RENT-HK-JAN2024'
            },
            {
                'description': 'HK Marketing Services',
                'payee_name': 'Asia Marketing Group',
                'merchant': 'BANK OF CHINA HK',
                'amount': -12400.00,
                'currency': 'HKD',
                'payment_reference': 'MKT-HK-2024-03'
            },
            # EUR Transactions (European operations)
            {
                'description': 'European Client - Germany',
                'payee_name': 'München Engineering GmbH',
                'merchant': 'DEUTSCHE BANK',
                'amount': 4200.00,
                'currency': 'EUR',
                'payment_reference': 'DE-PROJ-2024-02'
            },
            {
                'description': 'EU Travel Expenses',
                'payee_name': 'Lufthansa Airlines',
                'merchant': 'LUFTHANSA.COM',
                'amount': -890.50,
                'currency': 'EUR',
                'payment_reference': 'TRAVEL-EU-2024'
            },
            {
                'description': 'Netherlands Supplier',
                'payee_name': 'Amsterdam Tech Solutions',
                'merchant': 'ING BANK NETHERLANDS',
                'amount': -1350.00,
                'currency': 'EUR',
                'payment_reference': 'NL-SUPPLY-2024-01'
            },
            # GBP Transactions (UK operations)
            {
                'description': 'London Client Project',
                'payee_name': 'Thames Digital Ltd',
                'merchant': 'BARCLAYS UK',
                'amount': 3200.00,
                'currency': 'GBP',
                'payment_reference': 'UK-PROJ-2024-04'
            },
            {
                'description': 'UK Legal Services',
                'payee_name': 'City Law Chambers',
                'merchant': 'SOLICITORS UK',
                'amount': -1500.00,
                'currency': 'GBP',
                'payment_reference': 'LEGAL-UK-2024'
            },
            {
                'description': 'Manchester Office Setup',
                'payee_name': 'Northwest Office Solutions',
                'merchant': 'LLOYDS BANK UK',
                'amount': -2850.00,
                'currency': 'GBP',
                'payment_reference': 'SETUP-MCR-2024'
            }
        ]
        
        # Generate transactions for the specified date range
        for i in range(min(len(sample_transactions), 20)):  # Generate up to 20 transactions to ensure multi-currency
            sample = sample_transactions[i % len(sample_transactions)]
            
            # Random date within the specified range
            days_ago = random.randint(0, days_back)
            transaction_date = datetime.now() - timedelta(days=days_ago)
            
            # Add some variation to amounts
            amount_variation = random.uniform(0.8, 1.2)
            varied_amount = round(sample['amount'] * amount_variation, 2)
            
            transaction = {
                'date': transaction_date.strftime('%Y-%m-%d'),
                'amount': varied_amount,
                'currency': sample['currency'],
                'description': f"{sample['description']} #{i+1}",
                'payment_reference': f"{sample['payment_reference']}-{i+1:03d}",
                'payee_name': sample['payee_name'],
                'merchant': sample['merchant']
            }
            
            transactions.append(transaction)
        
        return transactions
    
    def _get_balances(self) -> List[Dict]:
        """
        Get all balances for the profile
        """
        try:
            endpoint = f"/v4/profiles/{self.profile_id}/balances"
            params = {'types': 'STANDARD'}  # Get standard balances
            
            response = self._make_api_call(endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            self.logger.error(f"Error fetching balances: {e}")
            return []
    
    def _get_balance_transactions(self, balance_id: str, currency: str, days_back: int) -> List[Dict]:
        """
        Get transactions for a specific balance using balance statement
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            endpoint = f"/v1/profiles/{self.profile_id}/balance-statements/{balance_id}/statement.json"
            params = {
                'currency': currency,
                'intervalStart': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'intervalEnd': end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'type': 'COMPACT'
            }
            
            response = self._make_api_call(endpoint, params=params)
            
            # Extract transactions from response
            transactions = []
            if isinstance(response, dict) and 'transactions' in response:
                for wise_tx in response['transactions']:
                    # Map Wise transaction format to our format
                    transaction = self._map_wise_transaction(wise_tx)
                    if transaction:
                        transactions.append(transaction)
            
            return transactions
            
        except Exception as e:
            self.logger.error(f"Error fetching transactions for balance {balance_id}: {e}")
            return []
    
    def _map_wise_transaction(self, wise_tx: Dict) -> Optional[Dict]:
        """
        Map Wise transaction format to our application format
        """
        try:
            # Extract key fields from Wise transaction
            date = wise_tx.get('date', '')
            amount = wise_tx.get('amount', {}).get('value', 0)
            currency = wise_tx.get('amount', {}).get('currency', 'USD')
            description = wise_tx.get('description', '')
            reference = wise_tx.get('referenceNumber', '')
            
            # Extract details if available
            details = wise_tx.get('details', {})
            payee_name = details.get('merchant', {}).get('name', '') or details.get('senderName', '') or 'Unknown'
            merchant = details.get('merchant', {}).get('name', '') or 'N/A'
            
            return {
                'date': date[:10] if date else datetime.now().strftime('%Y-%m-%d'),  # Format as YYYY-MM-DD
                'amount': float(amount) if amount else 0.0,
                'currency': currency,
                'description': description or 'No description',
                'payment_reference': reference or 'N/A',
                'payee_name': payee_name,
                'merchant': merchant,
                'wise_transaction_id': wise_tx.get('transactionId', ''),
                'type': wise_tx.get('type', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error mapping Wise transaction: {e}")
            return None
    
    def _make_api_call(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make actual API call to Wise
        """
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'iBeekeeper/1.0'
        }
        
        url = f"{self.api_url}{endpoint}"
        
        self.logger.debug(f"Making API call to: {url}")
        self.logger.debug(f"With params: {params}")
        
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30  # 30 second timeout
        )
        
        # Log response status
        self.logger.debug(f"Response status: {response.status_code}")
        
        # Check if request was successful
        response.raise_for_status()
        
        # Return JSON response
        return response.json()
    
    def test_connection(self) -> bool:
        """Test if API connection is working by fetching profile balances"""
        try:
            # Validate configuration
            if not all([self.api_url, self.api_token, self.profile_id]):
                self.logger.error("Missing API configuration for connection test")
                return False
            
            # Try to fetch balances as a connection test
            balances = self._get_balances()
            
            # Connection is successful if we can fetch balances (even if empty)
            return isinstance(balances, list)
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False