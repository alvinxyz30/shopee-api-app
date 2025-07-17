#!/usr/bin/env python
"""
Shopee API Integration Application
Main entry point untuk menjalankan aplikasi Flask
"""

import os
import sys
from flask import Flask
from app import app, db
from scheduler import TokenRefreshScheduler
from shopee_api import ShopeeAPI
from config import Config

def create_app():
    """Create and configure Flask application"""
    # Initialize scheduler
    shopee_api = ShopeeAPI(
        partner_id=Config.SHOPEE_PARTNER_ID,
        partner_key=Config.SHOPEE_PARTNER_KEY,
        base_url=Config.SHOPEE_BASE_URL
    )
    
    scheduler = TokenRefreshScheduler(shopee_api)
    
    # Start scheduler in production
    if not app.debug:
        scheduler.start()
    
    return app, scheduler

def init_database():
    """Initialize database tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    # Create application and scheduler
    app, scheduler = create_app()
    
    try:
        # Initialize database if needed
        if '--init-db' in sys.argv:
            init_database()
            sys.exit(0)
        
        # Check if all required environment variables are set
        required_vars = [
            'SHOPEE_PARTNER_ID',
            'SHOPEE_PARTNER_KEY', 
            'SHOPEE_REDIRECT_URL',
            'SHOPEE_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(Config, var):
                missing_vars.append(var)
        
        if missing_vars:
            print("ERROR: Missing required environment variables:")
            for var in missing_vars:
                print(f"  - {var}")
            print("\nPlease check your .env file and ensure all variables are set.")
            sys.exit(1)
        
        # Print startup information
        print("=" * 50)
        print("Shopee API Integration Application")
        print("=" * 50)
        print(f"Partner ID: {Config.SHOPEE_PARTNER_ID}")
        print(f"Base URL: {Config.SHOPEE_BASE_URL}")
        print(f"Redirect URL: {Config.SHOPEE_REDIRECT_URL}")
        print(f"Database: {Config.SQLALCHEMY_DATABASE_URI}")
        print("=" * 50)
        
        # Start Flask application
        print("Starting Flask application...")
        
        # Get host and port from environment or use defaults
        host = os.environ.get('FLASK_HOST', '0.0.0.0')
        port = int(os.environ.get('FLASK_PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
        
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\nShutting down application...")
        
    finally:
        # Stop scheduler
        if 'scheduler' in locals():
            scheduler.stop()
        print("Application stopped.")