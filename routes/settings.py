from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import db, AppSettings
from services.wise_api import WiseAPIService
from utils.validation import InputValidator, ValidationError
import re

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    """Settings page with Wise API configuration"""
    
    # Get current user's Wise configuration
    wise_config = current_user.get_wise_config()
    
    # Mask API token for display (show only first 8 and last 4 characters)
    masked_token = ''
    if wise_config['api_token']:
        token = wise_config['api_token']
        if len(token) > 12:
            masked_token = token[:8] + '...' + token[-4:]
        else:
            masked_token = token[:4] + '...' if len(token) > 4 else token
    
    wise_config['masked_token'] = masked_token
    
    return render_template('settings.html', wise_config=wise_config)

@settings_bp.route('/settings/wise', methods=['POST'])
@login_required
def save_wise_settings():
    """Save Wise API configuration"""
    try:
        # Get form data
        api_url = request.form.get('api_url', '').strip()
        api_token = request.form.get('api_token', '').strip()
        entity_number = request.form.get('entity_number', '').strip()
        is_sandbox = request.form.get('is_sandbox') == 'on'
        
        # Validate API URL
        if not api_url:
            flash('API URL is required', 'error')
            return redirect(url_for('settings.settings'))
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(api_url):
            flash('Please enter a valid API URL (must start with http:// or https://)', 'error')
            return redirect(url_for('settings.settings'))
        
        # Validate API token
        if api_token and len(api_token) < 10:
            flash('API token seems too short. Please check your token.', 'warning')
        
        # Validate Profile ID (required and should be numeric)
        if not entity_number:
            flash('Profile ID is required for Wise API access', 'error')
            return redirect(url_for('settings.settings'))
        
        if not entity_number.isdigit():
            flash('Profile ID should contain only numbers', 'error')
            return redirect(url_for('settings.settings'))
        
        # Save configuration for current user
        AppSettings.set_user_setting(current_user.id, 'WISE_API_URL', api_url)
        AppSettings.set_user_setting(current_user.id, 'WISE_API_TOKEN', api_token)
        AppSettings.set_user_setting(current_user.id, 'WISE_ENTITY_NUMBER', entity_number)
        AppSettings.set_user_setting(current_user.id, 'WISE_SANDBOX_MODE', is_sandbox)
        
        flash('Wise API settings saved successfully!', 'success')
        
    except Exception as e:
        flash(f'Error saving settings: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('settings.settings'))

@settings_bp.route('/settings/wise/test', methods=['POST'])
@login_required
def test_wise_connection():
    """Test Wise API connection"""
    try:
        # Get current user's configuration
        wise_config = current_user.get_wise_config()
        
        if not wise_config['api_token']:
            return jsonify({
                'success': False,
                'message': 'No API token configured. Please save your settings first.'
            })
        
        # Initialize Wise API service with current settings
        wise_service = WiseAPIService(
            api_url=wise_config['api_url'],
            api_token=wise_config['api_token']
        )
        
        # Test connection
        is_connected = wise_service.test_connection()
        
        if is_connected:
            return jsonify({
                'success': True,
                'message': 'Successfully connected to Wise API!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to connect to Wise API. Please check your credentials.'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        })

@settings_bp.route('/settings/wise/clear', methods=['POST'])
@login_required
def clear_wise_settings():
    """Clear Wise API configuration"""
    try:
        AppSettings.set_user_setting(current_user.id, 'WISE_API_URL', 'https://api.wise.com')
        AppSettings.set_user_setting(current_user.id, 'WISE_API_TOKEN', '')
        AppSettings.set_user_setting(current_user.id, 'WISE_ENTITY_NUMBER', '')
        AppSettings.set_user_setting(current_user.id, 'WISE_SANDBOX_MODE', False)
        
        flash('Wise API settings cleared successfully!', 'success')
        
    except Exception as e:
        flash(f'Error clearing settings: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('settings.settings'))

@settings_bp.route('/api/settings/wise')
@login_required
def get_wise_settings_api():
    """API endpoint to get Wise configuration (for AJAX)"""
    wise_config = current_user.get_wise_config()
    
    # Don't send sensitive data in API response
    return jsonify({
        'api_url': wise_config['api_url'],
        'has_token': bool(wise_config['api_token']),
        'has_entity': bool(wise_config['entity_number']),
        'is_sandbox': wise_config['is_sandbox']
    })