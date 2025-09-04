from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import os
import tempfile
import csv
import zipfile
import shutil
from models import db, Transaction, TransactionCode

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
def reports():
    """Reports page with date range selection and export options"""
    
    # Default date range (year to date)
    today = datetime.now()
    default_start = today.replace(month=1, day=1)
    default_end = today
    
    # Get date range from request
    start_date_str = request.args.get('start_date', default_start.strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', default_end.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'error')
        start_date = default_start.date()
        end_date = default_end.date()
    
    # Get coded transactions in date range (user-filtered)
    coded_transactions = db.session.query(Transaction, TransactionCode).join(
        TransactionCode
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date.desc()).all()
    
    # Calculate totals by currency
    currency_totals = {}
    
    for transaction, code in coded_transactions:
        currency = transaction.currency or 'USD'  # Default to USD if no currency
        
        if currency not in currency_totals:
            currency_totals[currency] = {'revenue': 0, 'expense': 0}
        
        if code.category_name == 'Revenue':
            currency_totals[currency]['revenue'] += transaction.amount
        elif code.category_name == 'Expense':
            currency_totals[currency]['expense'] += abs(transaction.amount)  # Make expenses positive
    
    # For backward compatibility, calculate totals in primary currency (first currency found or USD)
    primary_currency = next(iter(currency_totals.keys())) if currency_totals else 'USD'
    revenue_total = currency_totals.get(primary_currency, {}).get('revenue', 0)
    expense_total = currency_totals.get(primary_currency, {}).get('expense', 0)
    
    profit = revenue_total - expense_total
    
    # Prepare data for template
    report_data = {
        'transactions': coded_transactions,
        'revenue_total': revenue_total,
        'expense_total': expense_total,
        'net_profit': profit,
        'currency_totals': currency_totals,
        'primary_currency': primary_currency,
        'start_date': start_date,
        'end_date': end_date,
        'total_transactions': len(coded_transactions)
    }
    
    return render_template('reports.html', 
                         report_data=report_data,
                         start_date_str=start_date_str,
                         end_date_str=end_date_str)

@reports_bp.route('/export/csv')
@login_required
def export_csv():
    """Export transactions to CSV file"""
    
    # Get date range from request
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date range for export', 'error')
        return redirect(url_for('reports.reports'))
    
    # Get coded transactions in date range (user-filtered)
    coded_transactions = db.session.query(Transaction, TransactionCode).join(
        TransactionCode
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date.asc()).all()
    
    if not coded_transactions:
        flash('No coded transactions found in the selected date range', 'warning')
        return redirect(url_for('reports.reports'))
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as tmp_file:
        writer = csv.writer(tmp_file)
        
        # Write header
        writer.writerow([
            'Date', 'Description', 'Amount', 'Currency', 'Category',
            'Payee Name', 'Merchant', 'Payment Reference', 'Notes', 'Documents'
        ])
        
        # Write data
        for transaction, code in coded_transactions:
            # Get document filenames
            document_names = [doc.filename for doc in transaction.documents]
            documents_str = '; '.join(document_names) if document_names else 'No documents'
            
            writer.writerow([
                transaction.date.strftime('%Y-%m-%d'),
                transaction.description,
                transaction.amount,
                transaction.currency,
                code.category_name,
                transaction.payee_name or '',
                transaction.merchant or '',
                transaction.payment_reference or '',
                code.notes or '',
                documents_str
            ])
        
        # Generate filename
        filename = f"bookkeeping_report_{start_date_str}_to_{end_date_str}.csv"
        
        return send_file(
            tmp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )

@reports_bp.route('/export/complete')
@login_required
def export_complete():
    """Export transactions with all associated PDF documents in a ZIP file"""
    
    # Get date range from request
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date range for export', 'error')
        return redirect(url_for('reports.reports'))
    
    # Get coded transactions in date range (user-filtered)
    coded_transactions = db.session.query(Transaction, TransactionCode).join(
        TransactionCode
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date.asc()).all()
    
    if not coded_transactions:
        flash('No reconciled transactions found in the selected date range', 'warning')
        return redirect(url_for('reports.reports'))
    
    # Create temporary directory for organizing files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create CSV file
        csv_filename = f"transactions_{start_date_str}_to_{end_date_str}.csv"
        csv_path = os.path.join(temp_dir, csv_filename)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            
            # Write header
            writer.writerow([
                'Date', 'Description', 'Amount', 'Currency', 'Category',
                'Payee Name', 'Merchant', 'Payment Reference', 'Notes', 
                'Document Files', 'Document Count'
            ])
            
            # Write data and collect document info
            documents_dir = os.path.join(temp_dir, 'documents')
            os.makedirs(documents_dir, exist_ok=True)
            
            for transaction, code in coded_transactions:
                # Get document filenames
                document_names = []
                document_count = 0
                
                for doc in transaction.documents:
                    if os.path.exists(doc.file_path):
                        # Create a unique filename for the ZIP
                        file_extension = os.path.splitext(doc.filename)[1]
                        unique_filename = f"T{transaction.id}_{doc.id}_{doc.filename}"
                        
                        # Copy document to temp directory
                        dest_path = os.path.join(documents_dir, unique_filename)
                        try:
                            shutil.copy2(doc.file_path, dest_path)
                            document_names.append(unique_filename)
                            document_count += 1
                        except Exception as e:
                            print(f"Error copying file {doc.file_path}: {e}")
                            document_names.append(f"ERROR: {doc.filename}")
                
                documents_str = '; '.join(document_names) if document_names else 'No documents'
                
                writer.writerow([
                    transaction.date.strftime('%Y-%m-%d'),
                    transaction.description,
                    transaction.amount,
                    transaction.currency,
                    code.category_name,
                    transaction.payee_name or '',
                    transaction.merchant or '',
                    transaction.payment_reference or '',
                    code.notes or '',
                    documents_str,
                    document_count
                ])
        
        # Create summary file
        summary_filename = f"summary_{start_date_str}_to_{end_date_str}.txt"
        summary_path = os.path.join(temp_dir, summary_filename)
        
        # Calculate totals by currency
        currency_totals = {}
        for t, c in coded_transactions:
            currency = t.currency or 'USD'
            if currency not in currency_totals:
                currency_totals[currency] = {'revenue': 0, 'expense': 0}
            
            if c.category_name == 'Revenue':
                currency_totals[currency]['revenue'] += t.amount
            elif c.category_name == 'Expense':
                currency_totals[currency]['expense'] += abs(t.amount)
        
        # Use primary currency for summary (first currency found or USD)
        primary_currency = next(iter(currency_totals.keys())) if currency_totals else 'USD'
        revenue_total = currency_totals.get(primary_currency, {}).get('revenue', 0)
        expense_total = currency_totals.get(primary_currency, {}).get('expense', 0)
        profit = revenue_total - expense_total
        total_documents = sum(len(t.documents) for t, c in coded_transactions)
        
        with open(summary_path, 'w', encoding='utf-8') as summary_file:
            summary_file.write(f"Bookkeeping Export Summary\n")
            summary_file.write(f"========================\n\n")
            summary_file.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            summary_file.write(f"Period: {start_date_str} to {end_date_str}\n\n")
            summary_file.write(f"Financial Summary:\n")
            if len(currency_totals) > 1:
                summary_file.write(f"** Multi-Currency Report **\n")
                for curr, totals in currency_totals.items():
                    curr_profit = totals['revenue'] - totals['expense']
                    summary_file.write(f"- {curr} Revenue: {totals['revenue']:.2f}\n")
                    summary_file.write(f"- {curr} Expenses: {totals['expense']:.2f}\n")
                    summary_file.write(f"- {curr} Profit: {curr_profit:.2f}\n")
                summary_file.write(f"\nPrimary Currency ({primary_currency}) Summary:\n")
            summary_file.write(f"- Total Revenue: {primary_currency} {revenue_total:.2f}\n")
            summary_file.write(f"- Total Expenses: {primary_currency} {expense_total:.2f}\n")
            summary_file.write(f"- Profit: {primary_currency} {profit:.2f}\n\n")
            summary_file.write(f"Transaction Details:\n")
            summary_file.write(f"- Total Transactions: {len(coded_transactions)}\n")
            summary_file.write(f"- Total Documents: {total_documents}\n\n")
            summary_file.write(f"Files Included:\n")
            summary_file.write(f"- {csv_filename} (transaction data)\n")
            summary_file.write(f"- documents/ folder (all PDF invoices/receipts)\n")
            summary_file.write(f"- {summary_filename} (this summary)\n")
        
        # Create ZIP file
        zip_filename = f"bookkeeping_complete_{start_date_str}_to_{end_date_str}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add CSV file
            zipf.write(csv_path, csv_filename)
            
            # Add summary file
            zipf.write(summary_path, summary_filename)
            
            # Add all documents
            if os.path.exists(documents_dir):
                for filename in os.listdir(documents_dir):
                    file_path = os.path.join(documents_dir, filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, f"documents/{filename}")
        
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )