from flask import Blueprint, render_template, flash, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
import csv
import io
import os
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
    
    # Get stats for dashboard (user-filtered) - optimized queries
    from sqlalchemy import func
    from models import Document
    
    # Single query for total transactions
    total_transactions = db.session.query(func.count(Transaction.id)).filter(
        Transaction.user_id == current_user.id
    ).scalar() or 0
    
    # Query for reconciled transactions (those with documents)
    reconciled_transactions = db.session.query(func.count(Transaction.id)).join(
        Document, Transaction.documents
    ).filter(Transaction.user_id == current_user.id).scalar() or 0
    
    # Calculate unreconciled
    unreconciled_transactions = total_transactions - reconciled_transactions
    
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
        # Use logging instead of print statements for production
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Bank sync initiated")
        logger.debug(f"API URL configured: {bool(wise_config['api_url'])}")
        logger.debug(f"Profile ID configured: {bool(wise_config['entity_number'])}")
        logger.debug(f"Token configured: {bool(wise_config['api_token'])}")
        logger.debug(f"Sandbox mode: {wise_config.get('is_sandbox', False)}")
        
        api_transactions = wise_service.get_transactions(days_back=30)
        
        logger.info(f"Received {len(api_transactions)} transactions")
        if api_transactions:
            logger.debug("Sample transaction structure received")
        
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
        # Use logging instead of print statements
        logger.info("Upload request initiated")
        logger.debug(f"User authenticated: {current_user.is_authenticated}")
        logger.debug(f"Form data keys: {list(request.form.keys())}")
        logger.debug(f"Files uploaded: {list(request.files.keys())}")
        
        upload_type = request.form.get('upload_type')
        logger.debug(f"Upload type: {upload_type}")
        
        if upload_type == 'single':
            return handle_single_transaction_upload()
        elif upload_type == 'csv':
            return handle_csv_upload()
        else:
            logger.warning(f"Unknown upload type: {upload_type}")
            flash('Invalid upload type specified.', 'error')
    
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
        logger.info("CSV upload handler started")
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            logger.error("No csv_file in request.files")
            flash('No CSV file selected.', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        file = request.files['csv_file']
        logger.info(f"Processing CSV file: {file.filename}")
        
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
        file.seek(0)  # Reset file pointer
        content = file.read().decode('utf-8')
        stream = io.StringIO(content)
        csv_reader = csv.DictReader(stream)
        
        # Validate CSV headers
        required_headers = ['date', 'description', 'amount']
        optional_headers = ['currency', 'payee_name', 'merchant', 'payment_reference']
        
        fieldnames = csv_reader.fieldnames
        logger.debug(f"CSV fieldnames found: {fieldnames}")
        
        if not fieldnames:
            flash('CSV file appears to be empty or invalid format.', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        # Case-insensitive header check
        csv_headers_lower = [h.lower().strip() for h in fieldnames]
        missing_headers = [h for h in required_headers if h.lower() not in csv_headers_lower]
        
        if missing_headers:
            flash(f'CSV must contain these required columns: {", ".join(missing_headers)}. Found: {", ".join(fieldnames)}', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        # Process transactions
        new_transactions = 0
        skipped_transactions = 0
        errors = []
        
        logger.info("Starting CSV row processing...")
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header row
            try:
                logger.debug(f"Processing row {row_num}")
                
                # Clean and extract data (case-insensitive)
                row_data = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Skip empty rows
                if not any(row_data.values()):
                    logger.debug(f"Skipping empty row {row_num}")
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
                
                logger.debug(f"Created transaction: {transaction.description}")
                db.session.add(transaction)
                new_transactions += 1
                
            except ValidationError as e:
                errors.append(f"Row {row_num}: {str(e)}")
            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid date or amount format")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # Commit successful transactions
        logger.info(f"CSV import summary - New: {new_transactions}, Skipped: {skipped_transactions}, Errors: {len(errors)}")
        
        if new_transactions > 0:
            try:
                db.session.commit()
                logger.info(f"Successfully committed {new_transactions} new transactions")
                
                # Verify transactions were actually saved
                saved_count = Transaction.query.filter_by(user_id=current_user.id).count()
                logger.debug(f"Total transactions in database for user: {saved_count}")
                
            except Exception as commit_error:
                logger.error(f"Database commit failed: {commit_error}")
                db.session.rollback()
                flash(f'Database error: Failed to save transactions. {str(commit_error)}', 'error')
                return redirect(url_for('main.upload_transactions'))
        else:
            logger.info("No new transactions to commit")
        
        # Show results
        if new_transactions > 0:
            flash(f'Successfully uploaded {new_transactions} new transactions!', 'success')
        elif skipped_transactions > 0 and len(errors) == 0:
            flash(f'No new transactions added - all {skipped_transactions} transactions were duplicates.', 'warning')
        elif len(errors) == 0:
            flash('No transactions found in CSV file.', 'warning')
        
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

@main_bp.route('/mass-delete-transactions', methods=['POST', 'GET'])
@login_required 
def mass_delete_transactions():
    """Delete multiple transactions - backup route in main blueprint"""
    
    # Handle GET requests for testing
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'message': 'Mass delete endpoint is working (main blueprint)',
            'method': 'GET'
        })
    
    try:
        logger.info("Mass delete request received")
        
        # Get transaction IDs from request - handle both JSON and form data
        if request.is_json:
            transaction_ids = request.json.get('transaction_ids', [])
        else:
            # Fallback for form data
            transaction_ids = request.form.getlist('transaction_ids')
        
        logger.debug(f"Processing deletion of {len(transaction_ids)} transactions")
        
        if not transaction_ids:
            return jsonify({
                'success': False,
                'message': 'No transactions selected for deletion'
            })
        
        # Validate that all IDs are integers
        try:
            transaction_ids = [int(tid) for tid in transaction_ids]
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid transaction IDs provided'
            })
        
        # Query transactions that belong to the current user
        transactions = Transaction.query.filter(
            Transaction.id.in_(transaction_ids),
            Transaction.user_id == current_user.id
        ).all()
        
        if not transactions:
            return jsonify({
                'success': False,
                'message': 'No valid transactions found for deletion'
            })
        
        # Delete associated documents first
        deleted_count = 0
        for transaction in transactions:
            # Delete associated documents
            for document in transaction.documents:
                try:
                    if os.path.exists(document.file_path):
                        os.remove(document.file_path)
                except OSError:
                    pass  # Continue even if file deletion fails
            
            # Delete the transaction (cascade will handle documents and transaction_codes)
            db.session.delete(transaction)
            deleted_count += 1
        
        # Commit all deletions
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} transaction(s)',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Mass delete error: {str(e)}")
        logger.debug(f"Error type: {type(e)}", exc_info=True)
        
        return jsonify({
            'success': False,
            'message': f'Error deleting transactions: {str(e)}'
        })

@main_bp.route('/test-delete', methods=['POST', 'GET'])
def test_delete():
    """Simple test endpoint to verify routing works"""
    if request.method == 'POST':
        return jsonify({
            'status': 'POST test working', 
            'method': 'POST',
            'received_data': str(request.get_data()),
            'is_json': request.is_json
        })
    return jsonify({'status': 'test endpoint working', 'message': 'This proves routes are accessible'})

@main_bp.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})

@main_bp.route('/debug-db')
@login_required
def debug_database():
    """Debug endpoint to test database connectivity and user transactions"""
    try:
        # Test database connection
        total_transactions = Transaction.query.count()
        user_transactions = Transaction.query.filter_by(user_id=current_user.id).count()
        
        # Test creating a simple transaction
        test_transaction = Transaction(
            user_id=current_user.id,
            date=datetime.now().date(),
            amount=1.00,
            currency='USD',
            description='Test transaction for debug',
            status='unreconciled'
        )
        
        db.session.add(test_transaction)
        db.session.commit()
        
        # Count again after adding
        new_user_transactions = Transaction.query.filter_by(user_id=current_user.id).count()
        
        # Clean up test transaction
        db.session.delete(test_transaction)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'user_id': current_user.id,
            'total_transactions_in_db': total_transactions,
            'user_transactions_before': user_transactions,
            'user_transactions_after_test': new_user_transactions,
            'database_write_test': 'SUCCESS'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'database_write_test': 'FAILED'
        })