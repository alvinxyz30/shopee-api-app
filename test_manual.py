#!/usr/bin/env python
"""
Manual testing script untuk testing fitur secara interactive
"""

import os
import sys
import time
from datetime import datetime, timedelta

def test_shopee_api_manual():
    """Manual test untuk Shopee API dengan real data"""
    print("🧪 MANUAL SHOPEE API TEST")
    print("=" * 50)
    
    from config import Config
    from shopee_api import ShopeeAPI
    
    # Initialize API
    api = ShopeeAPI(
        partner_id=Config.SHOPEE_PARTNER_ID,
        partner_key=Config.SHOPEE_PARTNER_KEY,
        base_url=Config.SHOPEE_BASE_URL
    )
    
    print("1. Testing auth URL generation...")
    auth_url = api.generate_auth_url(Config.SHOPEE_REDIRECT_URL)
    print(f"✅ Auth URL: {auth_url}")
    
    print("\n2. Testing signature generation...")
    timestamp = int(time.time())
    signature = api._generate_signature("/api/v2/shop/auth_partner", timestamp)
    print(f"✅ Signature: {signature}")
    
    # Test dengan test credentials jika tersedia
    if hasattr(Config, 'TEST_SHOP_ID') and Config.TEST_SHOP_ID:
        print(f"\n3. Available test shop ID: {Config.TEST_SHOP_ID}")
        print(f"   Test account: {getattr(Config, 'TEST_SHOP_ACCOUNT', 'Not set')}")
    
    print("\n💡 Untuk test lengkap:")
    print("   1. Copy auth URL ke browser")
    print("   2. Login dengan test credentials")
    print("   3. Dapatkan code dari callback")
    print("   4. Test get_access_token dengan code tersebut")

def test_database_operations():
    """Manual test untuk operasi database"""
    print("\n🗄️  MANUAL DATABASE TEST")
    print("=" * 50)
    
    from app import app, db
    from models import Shop, APILog, DataExport
    from datetime import datetime
    
    with app.app_context():
        print("1. Testing shop creation...")
        
        # Create test shop
        test_shop = Shop(
            shop_id="manual_test_123",
            shop_name="Manual Test Shop",
            shop_account="manual@test.com",
            access_token="test_token",
            refresh_token="test_refresh",
            expires_at=datetime.utcnow() + timedelta(hours=4)
        )
        
        try:
            db.session.add(test_shop)
            db.session.commit()
            print("✅ Test shop created")
            
            # Test token validation
            print(f"   Token valid: {test_shop.is_token_valid}")
            print(f"   Expires soon: {test_shop.token_expires_soon}")
            
            # Test API log creation
            print("\n2. Testing API log creation...")
            test_log = APILog(
                shop_id="manual_test_123",
                endpoint="/api/v2/test",
                method="GET",
                status_code=200,
                response_time=0.5
            )
            
            db.session.add(test_log)
            db.session.commit()
            print("✅ API log created")
            
            # Test export record
            print("\n3. Testing export record...")
            test_export = DataExport(
                shop_id="manual_test_123",
                export_type="orders",
                date_from=datetime.utcnow() - timedelta(days=7),
                date_to=datetime.utcnow(),
                total_records=100,
                status="completed"
            )
            
            db.session.add(test_export)
            db.session.commit()
            print("✅ Export record created")
            
            # Query tests
            print("\n4. Testing queries...")
            shops = Shop.query.filter_by(is_active=True).all()
            logs = APILog.query.filter_by(shop_id="manual_test_123").all()
            exports = DataExport.query.filter_by(shop_id="manual_test_123").all()
            
            print(f"   Active shops: {len(shops)}")
            print(f"   Test logs: {len(logs)}")
            print(f"   Test exports: {len(exports)}")
            
            # Cleanup
            print("\n5. Cleaning up...")
            DataExport.query.filter_by(shop_id="manual_test_123").delete()
            APILog.query.filter_by(shop_id="manual_test_123").delete()
            Shop.query.filter_by(shop_id="manual_test_123").delete()
            db.session.commit()
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"❌ Database test failed: {str(e)}")
            db.session.rollback()

def test_excel_export_manual():
    """Manual test untuk Excel export dengan sample data"""
    print("\n📊 MANUAL EXCEL EXPORT TEST")
    print("=" * 50)
    
    from utils import flatten_order_data, flatten_product_data, flatten_return_data, export_to_excel
    import tempfile
    import os
    
    # Sample data untuk testing
    sample_orders = []
    for i in range(5):
        order = {
            'order_sn': f'ORDER_{i+1:03d}',
            'order_status': ['COMPLETED', 'SHIPPED', 'TO_SHIP'][i % 3],
            'create_time': int((datetime.now() - timedelta(days=i)).timestamp()),
            'total_amount': 100000 + (i * 25000),
            'buyer_username': f'buyer_{i+1}',
            'payment_method': ['COD', 'CREDIT_CARD', 'BANK_TRANSFER'][i % 3],
            'item_list': [
                {
                    'item_name': f'Product {i+1}',
                    'item_sku': f'SKU_{i+1}',
                    'model_quantity': i + 1
                }
            ],
            'recipient_address': {
                'name': f'Recipient {i+1}',
                'phone': f'08123456{i+1:03d}',
                'full_address': f'Jl. Test No. {i+1}',
                'city': 'Jakarta',
                'state': 'DKI Jakarta'
            }
        }
        sample_orders.append(order)
    
    print("1. Testing order data flattening...")
    flattened_orders = [flatten_order_data(order) for order in sample_orders]
    print(f"✅ Flattened {len(flattened_orders)} orders")
    print(f"   Fields per order: {len(flattened_orders[0])}")
    
    # Sample products
    sample_products = []
    for i in range(3):
        product = {
            'item_id': 12345 + i,
            'item_name': f'Test Product {i+1}',
            'item_sku': f'PROD_{i+1}',
            'item_status': 'NORMAL',
            'category_list': [
                {'display_category_name': 'Electronics'},
                {'display_category_name': 'Gadgets'}
            ],
            'price_info': {
                'current_price': 50000 + (i * 10000),
                'original_price': 60000 + (i * 10000),
                'currency': 'IDR'
            },
            'stock_info': {
                'normal_stock': 100 - (i * 10),
                'reserved_stock': 5
            },
            'sales': 150 + (i * 50),
            'views': 1000 + (i * 200),
            'create_time': int((datetime.now() - timedelta(days=30-i)).timestamp())
        }
        sample_products.append(product)
    
    print("\n2. Testing product data flattening...")
    flattened_products = [flatten_product_data(product) for product in sample_products]
    print(f"✅ Flattened {len(flattened_products)} products")
    
    # Sample returns
    sample_returns = []
    for i in range(2):
        return_data = {
            'return_sn': f'RET_{i+1:03d}',
            'order_sn': f'ORDER_{i+1:03d}',
            'status': ['PROCESSING', 'COMPLETED'][i % 2],
            'create_time': int((datetime.now() - timedelta(days=i+1)).timestamp()),
            'return_amount': 25000 + (i * 15000),
            'reason': ['DEFECTIVE', 'WRONG_ITEM'][i % 2],
            'text_reason': f'Test reason {i+1}',
            'user': {
                'username': f'buyer_{i+1}',
                'user_id': f'user_{i+1}'
            },
            'item': {
                'item_name': f'Product {i+1}',
                'item_sku': f'SKU_{i+1}',
                'amount': 1
            }
        }
        sample_returns.append(return_data)
    
    print("\n3. Testing return data flattening...")
    flattened_returns = [flatten_return_data(return_data) for return_data in sample_returns]
    print(f"✅ Flattened {len(flattened_returns)} returns")
    
    # Test Excel export
    print("\n4. Testing Excel export...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Export orders
            orders_file = export_to_excel(flattened_orders, 'test_orders.xlsx', 'Orders')
            orders_size = os.path.getsize(orders_file) if os.path.exists(orders_file) else 0
            print(f"✅ Orders Excel: {orders_size} bytes")
            
            # Export products
            products_file = export_to_excel(flattened_products, 'test_products.xlsx', 'Products')
            products_size = os.path.getsize(products_file) if os.path.exists(products_file) else 0
            print(f"✅ Products Excel: {products_size} bytes")
            
            # Export returns
            returns_file = export_to_excel(flattened_returns, 'test_returns.xlsx', 'Returns')
            returns_size = os.path.getsize(returns_file) if os.path.exists(returns_file) else 0
            print(f"✅ Returns Excel: {returns_size} bytes")
            
            print("\n✅ All Excel exports successful!")
            
        except Exception as e:
            print(f"❌ Excel export failed: {str(e)}")
        finally:
            os.chdir(original_dir)

def test_web_interface_manual():
    """Manual test untuk web interface"""
    print("\n🌐 MANUAL WEB INTERFACE TEST")
    print("=" * 50)
    
    from app import app
    
    print("1. Testing Flask app creation...")
    print(f"✅ App name: {app.name}")
    print(f"✅ Debug mode: {app.debug}")
    print(f"✅ Secret key: {'Set' if app.secret_key else 'Not set'}")
    
    print("\n2. Testing routes...")
    with app.test_client() as client:
        routes_to_test = [
            ('/', 'Homepage'),
            ('/add_shop', 'Add Shop Page')
        ]
        
        for route, name in routes_to_test:
            try:
                response = client.get(route)
                print(f"✅ {name}: Status {response.status_code}")
                
                if response.status_code == 200:
                    content_length = len(response.data)
                    print(f"   Content length: {content_length} bytes")
                    
                    # Check for basic HTML structure
                    if b'<html' in response.data and b'</html>' in response.data:
                        print("   ✅ Valid HTML structure")
                    else:
                        print("   ⚠️  HTML structure incomplete")
                        
            except Exception as e:
                print(f"❌ {name}: Error {str(e)}")
    
    print("\n3. Testing template filters...")
    with app.app_context():
        from app import timestamp_to_date_filter
        
        test_timestamp = int(datetime.now().timestamp())
        result = timestamp_to_date_filter(test_timestamp)
        print(f"✅ Timestamp filter: {test_timestamp} → {result}")

def test_scheduler_manual():
    """Manual test untuk scheduler functionality"""
    print("\n⏰ MANUAL SCHEDULER TEST")
    print("=" * 50)
    
    from scheduler import TokenRefreshScheduler
    from shopee_api import ShopeeAPI
    from config import Config
    
    print("1. Creating scheduler...")
    api = ShopeeAPI(
        partner_id=Config.SHOPEE_PARTNER_ID,
        partner_key=Config.SHOPEE_PARTNER_KEY,
        base_url=Config.SHOPEE_BASE_URL
    )
    
    scheduler = TokenRefreshScheduler(api)
    print("✅ Scheduler created")
    
    print("\n2. Testing scheduler status...")
    status = scheduler.get_scheduler_status()
    print(f"✅ Running: {status.get('running', False)}")
    print(f"✅ Jobs: {len(status.get('jobs', []))}")
    
    print("\n3. Testing token status summary...")
    from app import app
    with app.app_context():
        summary = scheduler.get_token_status_summary()
        print(f"✅ Total shops: {summary.get('total_shops', 0)}")
        print(f"✅ Valid tokens: {summary.get('valid_tokens', 0)}")
        print(f"✅ Expired tokens: {summary.get('expired_tokens', 0)}")
    
    print("\n4. Testing scheduler start/stop...")
    try:
        scheduler.start()
        print("✅ Scheduler started")
        time.sleep(1)  # Give it a moment
        
        scheduler.stop()
        print("✅ Scheduler stopped")
    except Exception as e:
        print(f"⚠️  Scheduler control: {str(e)}")

def interactive_menu():
    """Menu interaktif untuk manual testing"""
    while True:
        print("\n" + "=" * 60)
        print("🧪 SHOPEE API - MANUAL TESTING MENU")
        print("=" * 60)
        print("1. Test Shopee API functionality")
        print("2. Test Database operations")
        print("3. Test Excel export")
        print("4. Test Web interface")
        print("5. Test Scheduler")
        print("6. Run all manual tests")
        print("0. Exit")
        print("-" * 60)
        
        try:
            choice = input("Pilih test (0-6): ").strip()
            
            if choice == '1':
                test_shopee_api_manual()
            elif choice == '2':
                test_database_operations()
            elif choice == '3':
                test_excel_export_manual()
            elif choice == '4':
                test_web_interface_manual()
            elif choice == '5':
                test_scheduler_manual()
            elif choice == '6':
                print("Running all manual tests...")
                test_shopee_api_manual()
                test_database_operations()
                test_excel_export_manual()
                test_web_interface_manual()
                test_scheduler_manual()
                print("\n🎉 All manual tests completed!")
            elif choice == '0':
                print("👋 Exiting manual test menu...")
                break
            else:
                print("❌ Invalid choice. Please select 0-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        input("\nPress Enter to continue...")

if __name__ == '__main__':
    # Set up path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'api':
            test_shopee_api_manual()
        elif command == 'database':
            test_database_operations()
        elif command == 'export':
            test_excel_export_manual()
        elif command == 'web':
            test_web_interface_manual()
        elif command == 'scheduler':
            test_scheduler_manual()
        elif command == 'all':
            test_shopee_api_manual()
            test_database_operations()
            test_excel_export_manual()
            test_web_interface_manual()
            test_scheduler_manual()
        else:
            print("Available commands: api, database, export, web, scheduler, all")
    else:
        # Interactive menu
        interactive_menu()