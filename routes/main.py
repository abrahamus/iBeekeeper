from flask import Blueprint, render_template, flash, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
import csv
import io
from models import db, Transaction, TransactionCode, User
from services.wise_api import WiseAPIService
from config import Config
from utils.transaction_deduplication import TransactionDeduplicator
from utils.validation import InputValidator, ValidationError

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    """Dashboard with overview stats and sync button"""
    
    # Get stats for dashboard (user-filtered)
    total_transactions = Transaction.query.filter_by(user_id=current_user.id).count()
    unreconciled_transactions = Transaction.query.filter_by(user_id=current_user.id).filter(~Transaction.documents.any()).count()
    reconciled_transactions = Transaction.query.filter_by(user_id=current_user.id).join(TransactionCode).count()
    
    # Get recent transactions (user-filtered)
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(5).all()
    
    # Calculate Year to Date totals BY CURRENCY (fixing the currency mixing bug)
    current_year_start = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get all transactions with their currencies for YTD period (user-filtered)
    ytd_transactions = db.session.query(Transaction, TransactionCode).join(TransactionCode).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= current_year_start
    ).all()
    
    # Calculate totals by currency
    currency_totals = {}
    for transaction, code in ytd_transactions:
        currency = transaction.currency or 'USD'
        
        if currency not in currency_totals:
            currency_totals[currency] = {'revenue': 0, 'expense': 0, 'profit': 0}
        
        if code.category_name == 'Revenue':
            currency_totals[currency]['revenue'] += transaction.amount
        elif code.category_name == 'Expense':
            currency_totals[currency]['expense'] += abs(transaction.amount)
    
    # Calculate profit for each currency
    for currency in currency_totals:
        currency_totals[currency]['profit'] = (
            currency_totals[currency]['revenue'] - currency_totals[currency]['expense']
        )
    
    # For backward compatibility, get primary currency totals
    primary_currency = next(iter(currency_totals.keys())) if currency_totals else 'USD'
    ytd_revenue = currency_totals.get(primary_currency, {}).get('revenue', 0)
    ytd_expenses = currency_totals.get(primary_currency, {}).get('expense', 0)
    profit = currency_totals.get(primary_currency, {}).get('profit', 0)
    
    stats = {
        'total_transactions': total_transactions,
        'unreconciled_transactions': unreconciled_transactions,
        'reconciled_transactions': reconciled_transactions,
        'ytd_revenue': ytd_revenue,
        'ytd_expenses': ytd_expenses,
        'profit': profit,
        'currency_totals': currency_totals,
        'primary_currency': primary_currency,
        'has_multiple_currencies': len(currency_totals) > 1
    }
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         recent_transactions=recent_transactions,
                         current_period=f"Year {current_year_start.year}")

@main_bp.route('/sync-bank')
@login_required
def sync_bank_transactions():
    """Sync transactions from Bank API"""
    try:
        # Get user's Wise API configuration
        wise_config = current_user.get_wise_config()
        
        if not wise_config['api_token']:
            flash('Wise API token not configured. Please configure your API settings first.', 'error')
            return redirect(url_for('settings.wise_settings'))
        
        # Initialize Wise API service with user's settings
        wise_service = WiseAPIService(
            api_url=wise_config['api_url'],
            api_token=wise_config['api_token'],
            profile_id=wise_config['entity_number']
        )
        
        # Fetch transactions from last 30 days
        api_transactions = wise_service.get_transactions(days_back=30)
        
        new_transactions = 0
        updated_transactions = 0
        
        for api_transaction in api_transactions:
            transaction_date = datetime.strptime(api_transaction['date'], '%Y-%m-%d').date()
            
            # Use robust duplicate detection (user-filtered)
            is_duplicate, existing_transaction, confidence = TransactionDeduplicator.is_duplicate(
                date=transaction_date,
                amount=api_transaction['amount'],
                description=api_transaction['description'],
                payment_reference=api_transaction.get('payment_reference', ''),
                payee_name=api_transaction.get('payee_name', ''),
                confidence_threshold=0.85,  # High confidence for bank sync
                user_id=current_user.id
            )
            
            if is_duplicate:
                # Update existing transaction with any additional information
                if api_transaction.get('payment_reference') and not existing_transaction.payment_reference:
                    existing_transaction.payment_reference = api_transaction.get('payment_reference', '')
                if api_transaction.get('payee_name') and not existing_transaction.payee_name:
                    existing_transaction.payee_name = api_transaction.get('payee_name', '')
                if api_transaction.get('merchant') and not existing_transaction.merchant:
                    existing_transaction.merchant = api_transaction.get('merchant', '')
                updated_transactions += 1
            else:
                # Create new transaction (with user_id)
                transaction = Transaction(
                    user_id=current_user.id,
                    date=transaction_date,
                    amount=api_transaction['amount'],
                    currency=api_transaction['currency'],
                    description=api_transaction['description'],
                    payment_reference=api_transaction.get('payment_reference', ''),
                    payee_name=api_transaction.get('payee_name', ''),
                    merchant=api_transaction.get('merchant', '')
                )
                db.session.add(transaction)
                new_transactions += 1
        
        db.session.commit()
        
        flash(f'Successfully synced! Added {new_transactions} new transactions, updated {updated_transactions}.', 'success')
        
    except Exception as e:
        flash(f'Error syncing transactions: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/upload-transactions', methods=['GET', 'POST'])
@login_required
def upload_transactions():
    """Manual transaction upload page"""
    
    if request.method == 'POST':
        upload_type = request.form.get('upload_type')
        
        if upload_type == 'single':
            return handle_single_transaction_upload()
        elif upload_type == 'csv':
            return handle_csv_upload()
    
    return render_template('upload_transactions.html')

def handle_single_transaction_upload():
    """Handle single transaction manual entry"""
    try:
        # Get form data
        form_data = {
            'date': request.form.get('date'),
            'description': request.form.get('description', ''),
            'amount': request.form.get('amount', ''),
            'currency': request.form.get('currency', 'USD'),
            'payee_name': request.form.get('payee_name', ''),
            'merchant': request.form.get('merchant', ''),
            'payment_reference': request.form.get('payment_reference', '')
        }
        
        # Validate all data using the new validation system
        validated_data = InputValidator.validate_transaction_data(form_data)
        
        transaction_date = validated_data['date']
        amount = validated_data['amount']
        description = validated_data['description']
        currency = validated_data['currency']
        payee_name = validated_data['payee_name']
        merchant = validated_data['merchant']
        payment_reference = validated_data['payment_reference']
        
        # Use robust duplicate detection (user-filtered)
        is_duplicate, existing_transaction, confidence = TransactionDeduplicator.is_duplicate(
            date=transaction_date,
            amount=amount,
            description=description,
            payment_reference=payment_reference,
            payee_name=payee_name,
            confidence_threshold=0.8,  # Moderate confidence for manual entry
            user_id=current_user.id
        )
        
        if is_duplicate:
            flash(f'A similar transaction already exists (confidence: {confidence:.0%}). '
                  f'Existing transaction: "{existing_transaction.description}" on {existing_transaction.date}', 'warning')
            return redirect(url_for('main.upload_transactions'))
        
        # Create new transaction (with user_id)
        transaction = Transaction(
            user_id=current_user.id,
            date=transaction_date,
            amount=amount,
            currency=currency,
            description=description,
            payment_reference=payment_reference,
            payee_name=payee_name,
            merchant=merchant,
            status='unreconciled'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Transaction "{description}" added successfully!', 'success')
        
    except ValidationError as e:
        flash(f'Validation error: {str(e)}', 'error')
    except ValueError as e:
        flash('Invalid date or amount format. Please check your input.', 'error')
    except Exception as e:
        flash(f'Error adding transaction: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('main.upload_transactions'))

def handle_csv_upload():
    """Handle CSV file upload for bulk transactions"""
    try:
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash('No CSV file selected.', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        file = request.files['csv_file']
        
        # Validate file using the validation system
        is_valid, error_message = InputValidator.validate_file_upload(
            file, 
            allowed_extensions={'csv'}, 
            max_size_mb=5  # 5MB limit for CSV files
        )
        
        if not is_valid:
            flash(f'File validation error: {error_message}', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        # Read and process CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Validate CSV headers
        required_headers = ['date', 'description', 'amount']
        optional_headers = ['currency', 'payee_name', 'merchant', 'payment_reference']
        
        if not all(header.lower() in [h.lower() for h in csv_reader.fieldnames] for header in required_headers):
            flash(f'CSV must contain these required columns: {", ".join(required_headers)}', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        # Process transactions
        new_transactions = 0
        skipped_transactions = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header row
            try:
                # Clean and extract data (case-insensitive)
                row_data = {k.lower(): v.strip() if v else '' for k, v in row.items()}
                
                # Skip empty rows
                if not any(row_data.values()):
                    continue
                
                # Prepare data for validation
                transaction_data = {
                    'date': row_data.get('date', ''),
                    'description': row_data.get('description', ''),
                    'amount': row_data.get('amount', ''),
                    'currency': row_data.get('currency', 'USD'),
                    'payee_name': row_data.get('payee_name', ''),
                    'merchant': row_data.get('merchant', ''),
                    'payment_reference': row_data.get('payment_reference', '')
                }
                
                # Validate using the validation system
                validated_data = InputValidator.validate_transaction_data(transaction_data)
                
                transaction_date = validated_data['date']
                amount = validated_data['amount']
                description = validated_data['description']
                currency = validated_data['currency']
                payee_name = validated_data['payee_name']
                merchant = validated_data['merchant']
                payment_reference = validated_data['payment_reference']
                
                # Use robust duplicate detection (user-filtered)
                is_duplicate, existing_transaction, confidence = TransactionDeduplicator.is_duplicate(
                    date=transaction_date,
                    amount=amount,
                    description=description,
                    payment_reference=payment_reference,
                    payee_name=payee_name,
                    confidence_threshold=0.75,  # Lower threshold for CSV bulk import
                    user_id=current_user.id
                )
                
                if is_duplicate:
                    skipped_transactions += 1
                    continue
                
                # Create transaction (with user_id)
                transaction = Transaction(
                    user_id=current_user.id,
                    date=transaction_date,
                    amount=amount,
                    currency=currency,
                    description=description,
                    payment_reference=payment_reference,
                    payee_name=payee_name,
                    merchant=merchant,
                    status='unreconciled'
                )
                
                db.session.add(transaction)
                new_transactions += 1
                
            except ValidationError as e:
                errors.append(f"Row {row_num}: {str(e)}")
            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid date or amount format")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # Commit successful transactions
        if new_transactions > 0:
            db.session.commit()
        
        # Show results
        if new_transactions > 0:
            flash(f'Successfully uploaded {new_transactions} new transactions!', 'success')
        
        if skipped_transactions > 0:
            flash(f'Skipped {skipped_transactions} duplicate transactions.', 'warning')
        
        if errors:
            flash(f'Found {len(errors)} errors in CSV file. Check the format and try again.', 'error')
            for error in errors[:5]:  # Show first 5 errors
                flash(error, 'error')
            if len(errors) > 5:
                flash(f'... and {len(errors) - 5} more errors.', 'error')
        
    except Exception as e:
        flash(f'Error processing CSV file: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('main.upload_transactions'))

@main_bp.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})