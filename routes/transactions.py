from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from models import db, Transaction, Document, TransactionCode
from services.file_service import FileService
from config import Config
from utils.transaction_deduplication import TransactionDeduplicator
from utils.validation import InputValidator, SearchValidator, ValidationError

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    """List all transactions with filtering"""
    
    try:
        # Get and validate filter parameters
        status_filter = SearchValidator.validate_status_filter(request.args.get('status', 'all'))
        search_query = SearchValidator.validate_search_query(request.args.get('search', ''))
        category_filter = SearchValidator.validate_category_filter(request.args.get('category_filter', 'all'))
        
        # Validate date parameters
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = InputValidator.validate_date(start_date)
            except ValidationError as e:
                flash(f'Invalid start date: {str(e)}', 'warning')
                start_date = ''
        
        if end_date:
            try:
                end_date_obj = InputValidator.validate_date(end_date)
            except ValidationError as e:
                flash(f'Invalid end date: {str(e)}', 'warning')
                end_date = ''
        
        # Validate date range - start date should not be after end date
        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            flash('Start date cannot be after end date', 'warning')
            start_date_obj = None
            end_date_obj = None
            start_date = ''
            end_date = ''
                
    except ValidationError as e:
        flash(f'Filter validation error: {str(e)}', 'warning')
        # Use defaults
        status_filter = 'all'
        search_query = ''
        category_filter = 'all'
        start_date = ''
        end_date = ''
        start_date_obj = None
        end_date_obj = None
    
    # Base query (user-filtered)
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Check for conflicting filter combinations
    if ((status_filter in ['unreconciled', 'unmatched']) and 
        category_filter in ['revenue', 'expense']):
        # This is a logical contradiction - unreconciled transactions cannot have categories
        flash(f'No results: Unreconciled transactions cannot have category "{category_filter.title()}". Try "Status: All" or "Category: All/Undefined".', 'info')
        transactions = []  # Return empty result
    elif (status_filter in ['reconciled', 'coded'] and 
          category_filter == 'undefined'):
        # This is also contradictory - reconciled transactions must have categories
        flash('No results: Reconciled transactions must have categories. Try "Status: All/Unreconciled" or "Category: Revenue/Expense".', 'info')
        transactions = []  # Return empty result
    else:
        # Apply filters in the correct order based on combination
        
        # Determine if we need a join or outerjoin based on filter combination
        if (status_filter in ['reconciled', 'coded'] or 
            category_filter in ['revenue', 'expense']):
            # Need TransactionCode to exist
            query = query.join(TransactionCode)
            
            # Apply status filter (only if reconciled)
            # Note: No additional filtering needed since join already ensures reconciled status
            
            # Apply category filter
            if category_filter == 'revenue':
                query = query.filter(TransactionCode.category_name == 'Revenue')
            elif category_filter == 'expense':
                query = query.filter(TransactionCode.category_name == 'Expense')
                
        elif (status_filter in ['unreconciled', 'unmatched'] or 
              category_filter == 'undefined'):
            # Need TransactionCode to NOT exist
            query = query.outerjoin(TransactionCode).filter(TransactionCode.id == None)
        else:
            # No status or category filters, or status is 'all' - use outerjoin for full data
            query = query.outerjoin(TransactionCode)
        
        # Apply date range filter
        if start_date_obj:
            query = query.filter(Transaction.date >= start_date_obj)
                
        if end_date_obj:
            query = query.filter(Transaction.date <= end_date_obj)
        
        # Apply global search query
        if search_query:
            query = query.filter(
                db.or_(
                    Transaction.description.ilike(f'%{search_query}%'),
                    Transaction.payee_name.ilike(f'%{search_query}%'),
                    Transaction.merchant.ilike(f'%{search_query}%'),
                    Transaction.payment_reference.ilike(f'%{search_query}%')
                )
            )
        
        # Add pagination to handle large datasets
        page = request.args.get('page', 1, type=int)
        per_page = 50  # Show 50 transactions per page
        
        # Order by date (newest first) and paginate
        transactions = query.order_by(Transaction.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    return render_template('transactions.html', 
                         transactions=transactions,
                         status_filter=status_filter or 'all',
                         search_query=search_query or '',
                         start_date=start_date,
                         end_date=end_date,
                         category_filter=category_filter or 'all')

@transactions_bp.route('/transaction/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):
    """Transaction detail page for matching documents and coding"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    return render_template('transaction_detail.html', 
                         transaction=transaction,
                         categories=Config.CATEGORIES)

@transactions_bp.route('/transaction/<int:transaction_id>/upload', methods=['POST'])
@login_required
def upload_document(transaction_id):
    """Upload PDF document for a transaction"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))
        
        file = request.files['file']
        
        # Validate file using both systems for comprehensive validation
        is_valid, error_message = FileService.validate_file(file)
        if not is_valid:
            flash(error_message, 'error')
            return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))
        
        # Additional validation using the new system
        is_valid, error_message = InputValidator.validate_file_upload(
            file, Config.ALLOWED_EXTENSIONS, 16
        )
        if not is_valid:
            flash(f'Additional validation error: {error_message}', 'error')
            return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))
        
        # Save file
        original_filename, file_path, file_size = FileService.save_uploaded_file(file, transaction_id)
        
        # Create document record (with user_id)
        document = Document(
            user_id=current_user.id,
            filename=original_filename,
            file_path=file_path,
            file_size=file_size
        )
        db.session.add(document)
        
        # Link document to transaction
        transaction.documents.append(document)
        
        
        db.session.commit()
        
        flash(f'Document "{original_filename}" uploaded successfully!', 'success')
        
    except Exception as e:
        flash(f'Error uploading document: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))

@transactions_bp.route('/transaction/<int:transaction_id>/code', methods=['POST'])
@login_required
def code_transaction(transaction_id):
    """Code a transaction with category and notes"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        category = request.form.get('category')
        notes = request.form.get('notes', '').strip()
        
        # Validate using the validation system
        category = InputValidator.validate_category(category)
        notes = InputValidator.validate_notes(notes)
        
        # Check if transaction already has coding
        if transaction.transaction_code:
            # Update existing coding
            transaction.transaction_code.category_name = category
            transaction.transaction_code.notes = notes
            action = 'updated'
        else:
            # Create new coding (with user_id)
            transaction_code = TransactionCode(
                user_id=current_user.id,
                transaction_id=transaction_id,
                category_name=category,
                notes=notes
            )
            db.session.add(transaction_code)
            action = 'coded'
        
        # Update transaction status
        transaction.status = 'coded'
        
        db.session.commit()
        
        flash(f'Transaction {action} as {category}!', 'success')
        
    except ValidationError as e:
        flash(f'Validation error: {str(e)}', 'error')
    except Exception as e:
        flash(f'Error coding transaction: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))

@transactions_bp.route('/transaction/<int:transaction_id>/remove-document/<int:document_id>')
@login_required
def remove_document(transaction_id, document_id):
    """Remove a document from a transaction"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    
    try:
        # Remove document from transaction
        if document in transaction.documents:
            transaction.documents.remove(document)
        
        # Delete file from filesystem
        FileService.delete_file(document.file_path)
        
        # Delete document record
        db.session.delete(document)
        
        
        db.session.commit()
        
        flash('Document removed successfully!', 'success')
        
    except Exception as e:
        flash(f'Error removing document: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))

@transactions_bp.route('/transaction/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    """Edit transaction details"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Get form data and validate
            form_data = {
                'description': request.form.get('description', ''),
                'payee_name': request.form.get('payee_name', ''),
                'merchant': request.form.get('merchant', ''),
                'payment_reference': request.form.get('payment_reference', ''),
                'amount': request.form.get('amount', str(transaction.amount)),
                'currency': request.form.get('currency', transaction.currency)
            }
            
            # Validate all fields
            new_description = InputValidator.validate_description(form_data['description'])
            new_payee_name = InputValidator.validate_payee_name(form_data['payee_name'])
            new_merchant = InputValidator.validate_merchant(form_data['merchant'])
            new_payment_reference = InputValidator.validate_payment_reference(form_data['payment_reference'])
            new_amount = InputValidator.validate_amount(form_data['amount'])
            new_currency = InputValidator.validate_currency_code(form_data['currency'])
            
            # Check for duplicates if key fields changed
            key_fields_changed = (
                new_description != transaction.description or 
                new_amount != transaction.amount
            )
            
            if key_fields_changed:
                is_duplicate, existing_transaction, confidence = TransactionDeduplicator.is_duplicate(
                    date=transaction.date,
                    amount=new_amount,
                    description=new_description,
                    payment_reference=new_payment_reference,
                    payee_name=new_payee_name,
                    exclude_id=transaction_id,  # Exclude the current transaction
                    confidence_threshold=0.8,
                    user_id=current_user.id
                )
                
                if is_duplicate:
                    flash(f'Cannot update: Similar transaction already exists (confidence: {confidence:.0%}). '
                          f'Existing transaction: "{existing_transaction.description}" on {existing_transaction.date}', 'error')
                    return render_template('edit_transaction.html', transaction=transaction)
            
            # Apply updates
            transaction.description = new_description
            transaction.payee_name = new_payee_name
            transaction.merchant = new_merchant
            transaction.payment_reference = new_payment_reference
            transaction.amount = new_amount
            transaction.currency = new_currency
            
            db.session.commit()
            flash('Transaction updated successfully!', 'success')
            
            return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))
            
        except ValidationError as e:
            flash(f'Validation error: {str(e)}', 'error')
        except ValueError:
            flash('Invalid amount format. Please enter a valid number.', 'error')
        except Exception as e:
            flash(f'Error updating transaction: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('edit_transaction.html', transaction=transaction)

@transactions_bp.route('/transaction/<int:transaction_id>/delete')
@login_required
def delete_transaction(transaction_id):
    """Delete a transaction and all associated data"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        # Delete associated documents from filesystem
        for document in transaction.documents:
            FileService.delete_file(document.file_path)
            db.session.delete(document)
        
        # Delete transaction coding if exists
        if transaction.transaction_code:
            db.session.delete(transaction.transaction_code)
        
        # Delete the transaction
        db.session.delete(transaction)
        db.session.commit()
        
        flash('Transaction and associated data deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('transactions.list_transactions'))

@transactions_bp.route('/transaction/<int:transaction_id>/reset-coding')
@login_required
def reset_transaction_coding(transaction_id):
    """Reset/remove transaction coding while keeping documents"""
    
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        # Delete transaction coding if exists
        if transaction.transaction_code:
            db.session.delete(transaction.transaction_code)
            
            # Status will be determined by status_display property
            
            db.session.commit()
            flash('Transaction coding removed successfully!', 'success')
        else:
            flash('Transaction has no coding to remove.', 'warning')
            
    except Exception as e:
        flash(f'Error removing transaction coding: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('transactions.transaction_detail', transaction_id=transaction_id))

@transactions_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files - only to authenticated users who own them"""
    from models import Document
    import os
    
    # Security: Prevent directory traversal with comprehensive protection
    import urllib.parse
    from config import Config
    
    # Decode URL-encoded paths and normalize
    decoded_filename = urllib.parse.unquote(filename)
    normalized_path = os.path.normpath(decoded_filename)
    
    # Check for path traversal attempts
    if ('..' in filename or '..' in decoded_filename or 
        filename.startswith('/') or decoded_filename.startswith('/') or 
        normalized_path.startswith('/') or not normalized_path or
        os.path.isabs(normalized_path)):
        flash('Invalid file request', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Check if the file belongs to the current user using the safe normalized filename
    safe_filename = os.path.basename(normalized_path)
    document = Document.query.filter_by(
        user_id=current_user.id,
        filename=safe_filename
    ).first()
    
    if not document:
        flash('File not found or access denied', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Verify the file exists and path is secure
    if not os.path.exists(document.file_path):
        flash('File no longer exists', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Additional security: Ensure the resolved file path is within the upload directory
    upload_dir = os.path.abspath(os.getcwd() + '/' + Config.UPLOAD_FOLDER)
    resolved_file_path = os.path.abspath(document.file_path)
    
    if not resolved_file_path.startswith(upload_dir):
        flash('File access denied for security reasons', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Serve the file securely
    return send_file(document.file_path)

@transactions_bp.route('/mass-delete', methods=['POST', 'GET'])  # Allow GET for testing
@login_required
def mass_delete_transactions():
    """Delete multiple transactions"""
    
    # Handle GET requests for testing
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'message': 'Mass delete endpoint is working',
            'method': 'GET'
        })
    
    try:
        # Debug logging
        print(f"=== MASS DELETE REQUEST ===")
        print(f"Request method: {request.method}")
        print(f"Request data: {request.get_data()}")
        print(f"Request JSON: {request.get_json()}")
        
        # Get transaction IDs from request - handle both JSON and form data
        if request.is_json:
            transaction_ids = request.json.get('transaction_ids', [])
        else:
            # Fallback for form data
            transaction_ids = request.form.getlist('transaction_ids')
        
        print(f"Transaction IDs: {transaction_ids}")
        
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
        print(f"MASS DELETE ERROR: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Error deleting transactions: {str(e)}'
        })