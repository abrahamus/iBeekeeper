#!/usr/bin/env python3
"""
Database migration script for adding multi-user support
Run this ONCE to add user authentication and data segregation

WARNING: This will modify your existing database structure!
Make a backup before running this script.

Usage: python migrations/add_multi_user_support.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Transaction, TransactionCode, Document, AppSettings
import secrets

def create_default_admin_user():
    """Create a default admin user for existing data"""
    print("Creating default admin user...")
    
    admin_user = User(
        email='admin@bookkeeping.local',
        first_name='Admin',
        last_name='User'
    )
    admin_user.set_password('admin123')  # Change this!
    
    db.session.add(admin_user)
    db.session.commit()
    
    print(f"✅ Default admin user created: {admin_user.email}")
    print(f"   Password: admin123 (CHANGE THIS IMMEDIATELY!)")
    print(f"   User ID: {admin_user.id}")
    
    return admin_user

def migrate_existing_data_to_admin(admin_user):
    """Assign all existing data to the admin user"""
    print("Migrating existing data to admin user...")
    
    # Update all existing transactions
    transactions_updated = Transaction.query.update({'user_id': admin_user.id})
    print(f"   ✅ Updated {transactions_updated} transactions")
    
    # Update all existing transaction codes
    codes_updated = TransactionCode.query.update({'user_id': admin_user.id})
    print(f"   ✅ Updated {codes_updated} transaction codes")
    
    # Update all existing documents
    documents_updated = Document.query.update({'user_id': admin_user.id})
    print(f"   ✅ Updated {documents_updated} documents")
    
    # Update all existing app settings
    settings_updated = AppSettings.query.update({'user_id': admin_user.id})
    print(f"   ✅ Updated {settings_updated} app settings")
    
    db.session.commit()

def migrate_file_structure(admin_user):
    """Move existing uploads to user-specific directory"""
    print("Migrating file structure...")
    
    old_upload_path = "uploads"
    new_upload_path = admin_user.upload_path
    
    if os.path.exists(old_upload_path) and not os.path.exists(new_upload_path):
        import shutil
        print(f"   Moving {old_upload_path} to {new_upload_path}")
        
        # Create user directory structure
        os.makedirs(os.path.dirname(new_upload_path), exist_ok=True)
        
        # Move the uploads folder
        shutil.move(old_upload_path, new_upload_path)
        
        # Recreate base uploads directory
        os.makedirs("uploads", exist_ok=True)
        os.makedirs("uploads/users", exist_ok=True)
        
        print(f"   ✅ Files moved to {new_upload_path}")
    else:
        print("   ✅ File structure already migrated or no files to migrate")

def run_migration():
    """Run the complete migration"""
    app = create_app()
    
    with app.app_context():
        print("🚀 Starting multi-user migration...")
        print("=" * 50)
        
        try:
            # Create all new tables (including users)
            print("Creating database tables...")
            db.create_all()
            print("   ✅ Database tables created/updated")
            
            # Check if we need to migrate existing data
            existing_transactions = Transaction.query.count()
            existing_users = User.query.count()
            
            if existing_transactions > 0 and existing_users == 0:
                print(f"\nFound {existing_transactions} existing transactions without users")
                print("Creating admin user and migrating data...")
                
                # Create admin user
                admin_user = create_default_admin_user()
                
                # Migrate existing data
                migrate_existing_data_to_admin(admin_user)
                
                # Migrate file structure
                migrate_file_structure(admin_user)
                
            elif existing_users == 0:
                print("\nNo existing data found. Creating admin user...")
                admin_user = create_default_admin_user()
                
            else:
                print(f"\nFound {existing_users} existing users. Migration appears complete.")
            
            print("\n" + "=" * 50)
            print("✅ Multi-user migration completed successfully!")
            print("\nNext steps:")
            print("1. Update your Flask app to use Flask-Login")
            print("2. Add login_required decorators to protected routes")
            print("3. Update all database queries to filter by current_user.id")
            print("4. Test the login system thoroughly")
            print("5. Change the default admin password!")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    print("⚠️  WARNING: This will modify your database structure!")
    print("   Make sure you have a backup before proceeding.")
    
    # Auto-proceed for Claude Code environment
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("\nAuto-proceeding with migration...")
        run_migration()
    else:
        confirm = input("\nProceed with migration? (yes/no): ").lower().strip()
        if confirm == 'yes':
            run_migration()
        else:
            print("Migration cancelled.")