import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

class FileService:
    @staticmethod
    def save_uploaded_file(file, transaction_id: int) -> tuple:
        """
        Save uploaded PDF file and return (filename, file_path, file_size)
        """
        try:
            # Generate secure filename
            filename = secure_filename(file.filename)
            
            # Create unique filename to prevent conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            name, ext = os.path.splitext(filename)
            unique_filename = f"transaction_{transaction_id}_{timestamp}_{unique_id}{ext}"
            
            # Create directory structure: uploads/pdfs/YYYY/MM/
            current_date = datetime.now()
            year_month_dir = os.path.join(
                current_app.config['UPLOAD_FOLDER'],
                'pdfs',
                str(current_date.year),
                f"{current_date.month:02d}"
            )
            
            # Ensure directory exists
            os.makedirs(year_month_dir, exist_ok=True)
            
            # Full file path
            file_path = os.path.join(year_month_dir, unique_filename)
            
            # Save file
            file.save(file_path)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            return filename, file_path, file_size
            
        except Exception as e:
            raise Exception(f"Error saving file: {str(e)}")
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file from the filesystem"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    @staticmethod
    def get_file_url(file_path: str) -> str:
        """Generate URL for accessing uploaded file"""
        # Convert absolute path to relative URL
        if current_app.config['UPLOAD_FOLDER'] in file_path:
            relative_path = file_path.replace(current_app.config['UPLOAD_FOLDER'], '')
            return f"/uploads{relative_path}"
        return file_path
    
    @staticmethod
    def validate_file(file) -> tuple:
        """
        Validate uploaded file
        Returns (is_valid, error_message)
        """
        if not file:
            return False, "No file selected"
        
        if file.filename == '':
            return False, "No file selected"
        
        if not current_app.config.get('allowed_file', lambda x: True)(file.filename):
            return False, "Only PDF files are allowed"
        
        # Check file size (Flask's MAX_CONTENT_LENGTH handles this, but good to double-check)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        if file_size > max_size:
            return False, f"File too large. Maximum size is {max_size // (1024*1024)}MB"
        
        return True, ""