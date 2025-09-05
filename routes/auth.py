from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from utils.validation import InputValidator, ValidationError
import re
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'
        
        # Validate input
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('auth/login.html')
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('auth/login.html')
            
            # Login successful
            login_user(user, remember=remember_me)
            user.update_last_login()
            
            # Redirect to intended page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            # Get form data
            email = request.form.get('email', '').strip().lower()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validate required fields
            if not all([email, first_name, last_name, password, confirm_password]):
                flash('All fields are required', 'error')
                return render_template('auth/register.html')
            
            # Validate email format
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(email):
                flash('Please enter a valid email address', 'error')
                return render_template('auth/register.html')
            
            # Check if email already exists
            if User.query.filter_by(email=email).first():
                flash('An account with this email already exists', 'error')
                return render_template('auth/register.html')
            
            # Validate password strength
            if len(password) < 8:
                flash('Password must be at least 8 characters long', 'error')
                return render_template('auth/register.html')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('auth/register.html')
            
            # Validate names
            if len(first_name) < 2 or len(last_name) < 2:
                flash('First and last names must be at least 2 characters long', 'error')
                return render_template('auth/register.html')
            
            # Create new user
            user = User(
                email=email,
                first_name=first_name.title(),
                last_name=last_name.title()
            )
            user.set_password(password)
            
            # Create user's upload directory
            os.makedirs(user.upload_path, exist_ok=True)
            os.makedirs(os.path.join(user.upload_path, 'pdfs'), exist_ok=True)
            
            # Save to database
            db.session.add(user)
            db.session.commit()
            
            # Auto-login the new user
            login_user(user)
            user.update_last_login()
            
            flash(f'Welcome to Bookkeeping App, {user.first_name}! Your account has been created.', 'success')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'error')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    user_name = current_user.first_name
    logout_user()
    flash(f'Goodbye, {user_name}! You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        try:
            # Get form data
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validate names
            if not first_name or not last_name:
                flash('First and last names are required', 'error')
                return render_template('auth/edit_profile.html')
            
            if len(first_name) < 2 or len(last_name) < 2:
                flash('Names must be at least 2 characters long', 'error')
                return render_template('auth/edit_profile.html')
            
            # Update names
            current_user.first_name = first_name.title()
            current_user.last_name = last_name.title()
            
            # Handle password change
            if new_password:
                # Verify current password
                if not current_user.check_password(current_password):
                    flash('Current password is incorrect', 'error')
                    return render_template('auth/edit_profile.html')
                
                # Validate new password
                if len(new_password) < 8:
                    flash('New password must be at least 8 characters long', 'error')
                    return render_template('auth/edit_profile.html')
                
                if new_password != confirm_password:
                    flash('New passwords do not match', 'error')
                    return render_template('auth/edit_profile.html')
                
                # Update password
                current_user.set_password(new_password)
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return render_template('auth/edit_profile.html')

@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account (careful!)"""
    password = request.form.get('password', '')
    confirm_text = request.form.get('confirm_text', '').strip()
    
    # Verify password
    if not current_user.check_password(password):
        flash('Incorrect password', 'error')
        return redirect(url_for('auth.profile'))
    
    # Verify confirmation text
    if confirm_text != 'DELETE':
        flash('Please type "DELETE" to confirm account deletion', 'error')
        return redirect(url_for('auth.profile'))
    
    try:
        # Delete user's upload directory
        import shutil
        if os.path.exists(current_user.upload_path):
            shutil.rmtree(current_user.upload_path)
        
        # User deletion will cascade to all related data
        user_email = current_user.email
        db.session.delete(current_user)
        db.session.commit()
        
        # Logout and redirect
        logout_user()
        flash(f'Account {user_email} has been permanently deleted', 'info')
        return redirect(url_for('auth.register'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        # Get form data
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('auth.profile'))
        
        # Validate new password - consistent with registration requirements
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long', 'error')
            return redirect(url_for('auth.profile'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('auth.profile'))
        
        if current_password == new_password:
            flash('New password must be different from current password', 'error')
            return redirect(url_for('auth.profile'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing password: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))