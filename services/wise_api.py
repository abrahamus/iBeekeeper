import requests
from datetime import datetime, timedelta
from typing import List, Dict
import random
from models import AppSettings

class WiseAPIService:
    def __init__(self, api_url: str = None, api_token: str = None):
        # Use provided values or get from app settings
        if api_url and api_token:
            self.api_url = api_url
            self.api_token = api_token
        else:
            wise_config = AppSettings.get_wise_config()
            self.api_url = wise_config['api_url']
            self.api_token = wise_config['api_token']
        
        self.entity_number = AppSettings.get_setting('WISE_ENTITY_NUMBER', '')
        
    def get_transactions(self, days_back: int = 30) -> List[Dict]:
        """
        Fetch transactions from Wise API
        For now, returns dummy data that mimics real Wise transaction structure
        """
        try:
            # In real implementation, this would make API call to Wise
            # return self._make_api_call('/transactions', params={'days': days_back})
            
            # Dummy data for development
            return self._generate_dummy_transactions(days_back)
            
        except Exception as e:
            print(f"Error fetching transactions: {e}")
            return []
    
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
    
    def _make_api_call(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make actual API call to Wise (placeholder for real implementation)
        """
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{self.api_url}{endpoint}",
            headers=headers,
            params=params
        )
        
        response.raise_for_status()
        return response.json()
    
    def test_connection(self) -> bool:
        """Test if API connection is working"""
        try:
            # In real implementation, this would test actual API connection
            # For dummy implementation, always return True
            return True
        except:
            return False