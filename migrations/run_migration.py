#!/usr/bin/env python3
"""
Simple migration script for adding multi-user support
This avoids the model import issue by using raw SQL
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from werkzeug.security import generate_password_hash
import secrets

def get_db_path():
    """Get the database path"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'database.db')

def run_migration():
    """Run the complete migration using raw SQL"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print("❌ Database file not found. Please run the Flask app once to create the database.")
        return
    
    print("🚀 Starting multi-user migration...")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 1: Create the users table
        print("1. Creating users table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(120) NOT NULL UNIQUE,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            email_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            user_folder VARCHAR(32) NOT NULL UNIQUE,
            settings TEXT
        )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)')
        print("   ✅ Users table created")
        
        # Step 2: Add user_id columns to existing tables
        print("2. Adding user_id columns to existing tables...")
        
        # Check if columns already exist - secure parameterized query
        def column_exists(table_name, column_name):
            # PRAGMA statements don't support parameters, but we validate table names
            allowed_tables = ['transaction', 'transaction_code', 'document', 'app_settings']
            if table_name not in allowed_tables:
                raise ValueError(f"Invalid table name: {table_name}")
            
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        
        # Add user_id to transaction table
        if not column_exists('transaction', 'user_id'):
            cursor.execute('ALTER TABLE "transaction" ADD COLUMN user_id INTEGER')
            cursor.execute('CREATE INDEX IF NOT EXISTS ix_transaction_user_id ON "transaction" (user_id)')
            print("   ✅ Added user_id to transaction table")
        else:
            print("   ✅ user_id already exists in transaction table")
        
        # Add user_id to transaction_code table
        if not column_exists('transaction_code', 'user_id'):
            cursor.execute('ALTER TABLE transaction_code ADD COLUMN user_id INTEGER')
            cursor.execute('CREATE INDEX IF NOT EXISTS ix_transaction_code_user_id ON transaction_code (user_id)')
            print("   ✅ Added user_id to transaction_code table")
        else:
            print("   ✅ user_id already exists in transaction_code table")
        
        # Add user_id to document table
        if not column_exists('document', 'user_id'):
            cursor.execute('ALTER TABLE document ADD COLUMN user_id INTEGER')
            cursor.execute('CREATE INDEX IF NOT EXISTS ix_document_user_id ON document (user_id)')
            print("   ✅ Added user_id to document table")
        else:
            print("   ✅ user_id already exists in document table")
        
        # Add user_id to app_settings table
        if not column_exists('app_settings', 'user_id'):
            cursor.execute('ALTER TABLE app_settings ADD COLUMN user_id INTEGER')
            cursor.execute('CREATE INDEX IF NOT EXISTS ix_app_settings_user_id ON app_settings (user_id)')
            print("   ✅ Added user_id to app_settings table")
        else:
            print("   ✅ user_id already exists in app_settings table")
        
        # Step 3: Check if we need to create admin user and migrate data
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM "transaction"')
        transaction_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print("3. Creating default admin user...")
            
            # Generate unique user folder
            user_folder = secrets.token_urlsafe(16)
            password_hash = generate_password_hash('admin123')
            
            cursor.execute('''
            INSERT INTO users (email, first_name, last_name, password_hash, user_folder)
            VALUES (?, ?, ?, ?, ?)
            ''', ('admin@bookkeeping.local', 'Admin', 'User', password_hash, user_folder))
            
            admin_user_id = cursor.lastrowid
            print(f"   ✅ Default admin user created: admin@bookkeeping.local")
            print(f"      Password: admin123 (CHANGE THIS IMMEDIATELY!)")
            print(f"      User ID: {admin_user_id}")
            
            if transaction_count > 0:
                print("4. Migrating existing data to admin user...")
                
                # Update existing transactions
                cursor.execute('UPDATE "transaction" SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
                transactions_updated = cursor.rowcount
                print(f"   ✅ Updated {transactions_updated} transactions")
                
                # Update existing transaction codes
                cursor.execute('UPDATE transaction_code SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
                codes_updated = cursor.rowcount
                print(f"   ✅ Updated {codes_updated} transaction codes")
                
                # Update existing documents
                cursor.execute('UPDATE document SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
                documents_updated = cursor.rowcount
                print(f"   ✅ Updated {documents_updated} documents")
                
                # Update existing app settings
                cursor.execute('UPDATE app_settings SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
                settings_updated = cursor.rowcount
                print(f"   ✅ Updated {settings_updated} app settings")
                
                print("5. Migrating file structure...")
                # Create user-specific upload directory
                user_upload_path = f"uploads/users/{user_folder}"
                os.makedirs(user_upload_path, exist_ok=True)
                
                # Move existing files if they exist
                old_upload_path = "uploads"
                if os.path.exists(old_upload_path) and os.path.isdir(old_upload_path):
                    # Check if there are files to move
                    files_to_move = []
                    for root, dirs, files in os.walk(old_upload_path):
                        if root != old_upload_path or 'users' in dirs:
                            continue  # Skip the users subfolder
                        files_to_move.extend([os.path.join(root, f) for f in files])
                    
                    if files_to_move:
                        import shutil
                        for file_path in files_to_move:
                            try:
                                filename = os.path.basename(file_path)
                                new_path = os.path.join(user_upload_path, filename)
                                shutil.move(file_path, new_path)
                            except Exception as e:
                                print(f"      Warning: Could not move {file_path}: {e}")
                        print(f"   ✅ Moved {len(files_to_move)} files to user directory")
                    else:
                        print("   ✅ No files to migrate")
                else:
                    print("   ✅ No existing upload directory to migrate")
            else:
                print("   ✅ No existing data to migrate")
        else:
            print(f"3. Found {user_count} existing users. Migration appears complete.")
        
        # Step 4: Commit changes
        conn.commit()
        
        print("\n" + "=" * 50)
        print("✅ Multi-user migration completed successfully!")
        print("\nNext steps:")
        print("1. Login with: admin@bookkeeping.local / admin123")
        print("2. Change the admin password immediately!")
        print("3. Create additional user accounts as needed")
        print("4. Test the multi-user functionality")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("⚠️  WARNING: This will modify your database structure!")
    print("   Make sure you have a backup before proceeding.")
    print("\nRunning migration...")
    run_migration()