import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///shopee_app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Shopee API Configuration
    SHOPEE_PARTNER_ID = os.environ.get('SHOPEE_PARTNER_ID')
    SHOPEE_PARTNER_KEY = os.environ.get('SHOPEE_PARTNER_KEY')
    SHOPEE_REDIRECT_URL = os.environ.get('SHOPEE_REDIRECT_URL')
    SHOPEE_BASE_URL = os.environ.get('SHOPEE_BASE_URL')
    
    # Test Data
    TEST_SHOP_ID = os.environ.get('TEST_SHOP_ID')
    TEST_SHOP_ACCOUNT = os.environ.get('TEST_SHOP_ACCOUNT')
    TEST_SHOP_PASSWORD = os.environ.get('TEST_SHOP_PASSWORD')
    
    # Pagination
    ORDERS_PER_PAGE = 20
    PRODUCTS_PER_PAGE = 20
    RETURNS_PER_PAGE = 20