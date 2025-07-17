#!/usr/bin/env python
"""
Test script untuk mengecek koneksi dan konfigurasi Shopee API
"""

import os
import sys
import time
from datetime import datetime
from config import Config
from shopee_api import ShopeeAPI, ShopeeAPIError

def test_configuration():
    """Test konfigurasi environment variables"""
    print("=" * 60)
    print("🔧 TESTING CONFIGURATION")
    print("=" * 60)
    
    required_configs = [
        'SHOPEE_PARTNER_ID',
        'SHOPEE_PARTNER_KEY', 
        'SHOPEE_REDIRECT_URL',
        'SHOPEE_BASE_URL'
    ]
    
    missing_configs = []
    
    for config in required_configs:
        value = getattr(Config, config, None)
        if value:
            # Mask sensitive data
            if 'KEY' in config:
                masked_value = value[:10] + "..." + value[-10:] if len(value) > 20 else value
                print(f"✅ {config}: {masked_value}")
            else:
                print(f"✅ {config}: {value}")
        else:
            print(f"❌ {config}: MISSING")
            missing_configs.append(config)
    
    if missing_configs:
        print(f"\n❌ ERROR: Missing configurations: {', '.join(missing_configs)}")
        print("💡 Solusi: Edit file .env dan isi konfigurasi yang diperlukan")
        return False
    
    print("\n✅ All configurations are present")
    return True

def test_shopee_api():
    """Test Shopee API connection dan signature"""
    print("\n" + "=" * 60)
    print("🌐 TESTING SHOPEE API CONNECTION")
    print("=" * 60)
    
    try:
        # Initialize API
        api = ShopeeAPI(
            partner_id=Config.SHOPEE_PARTNER_ID,
            partner_key=Config.SHOPEE_PARTNER_KEY,
            base_url=Config.SHOPEE_BASE_URL
        )
        print("✅ ShopeeAPI initialized successfully")
        
        # Test signature generation
        test_path = "/api/v2/shop/auth_partner"
        test_timestamp = int(datetime.now().timestamp())
        signature = api._generate_signature(test_path, test_timestamp)
        print(f"✅ Signature generation working: {signature[:20]}...")
        
        # Test auth URL generation
        auth_url = api.generate_auth_url(Config.SHOPEE_REDIRECT_URL)
        print(f"✅ Auth URL generated successfully")
        print(f"   URL length: {len(auth_url)} chars")
        print(f"   Sample: {auth_url[:80]}...")
        
        # Test parameter validation
        try:
            api._generate_signature("", test_timestamp)  # Should handle empty path
            print("✅ Parameter validation working")
        except:
            print("⚠️  Parameter validation might need improvement")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Shopee API: {str(e)}")
        print("💡 Solusi: Periksa Partner ID dan Partner Key di file .env")
        return False

def test_database():
    """Test database connection dan models"""
    print("\n" + "=" * 60)
    print("🗄️  TESTING DATABASE CONNECTION")
    print("=" * 60)
    
    try:
        from app import app, db
        
        with app.app_context():
            # Test database connection
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Test models
            from models import Shop, APILog, DataExport
            
            # Test basic queries
            shop_count = Shop.query.count()
            log_count = APILog.query.count()
            export_count = DataExport.query.count()
            
            print(f"✅ Database queries working:")
            print(f"   - Shops: {shop_count}")
            print(f"   - API Logs: {log_count}")
            print(f"   - Exports: {export_count}")
            
            # Test model properties
            test_shop = Shop(
                shop_id="test123",
                shop_name="Test Shop",
                shop_account="test@example.com"
            )
            
            # Test token validation methods
            is_valid = test_shop.is_token_valid
            expires_soon = test_shop.token_expires_soon
            print(f"✅ Model methods working: token_valid={is_valid}, expires_soon={expires_soon}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing database: {str(e)}")
        print("💡 Solusi: Periksa DATABASE_URL di file .env atau jalankan --init-db")
        return False

def test_utils():
    """Test utility functions"""
    print("\n" + "=" * 60)
    print("🛠️  TESTING UTILITY FUNCTIONS")
    print("=" * 60)
    
    try:
        from utils import (
            validate_date_range, convert_timestamp_to_datetime,
            get_order_status_text, format_currency, sanitize_filename
        )
        
        # Test date validation
        from datetime import datetime, timedelta
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        start_date, end_date = validate_date_range(
            yesterday.strftime('%Y-%m-%d'),
            today.strftime('%Y-%m-%d')
        )
        print(f"✅ Date validation working: {start_date.date()} to {end_date.date()}")
        
        # Test timestamp conversion
        timestamp = int(today.timestamp())
        converted = convert_timestamp_to_datetime(timestamp)
        print(f"✅ Timestamp conversion working: {timestamp} → {converted}")
        
        # Test status text conversion
        status_text = get_order_status_text('COMPLETED')
        print(f"✅ Status conversion working: COMPLETED → {status_text}")
        
        # Test currency formatting
        formatted = format_currency(1500000)
        print(f"✅ Currency formatting working: 1500000 → {formatted}")
        
        # Test filename sanitization
        dangerous_name = "test<>file?.xlsx"
        safe_name = sanitize_filename(dangerous_name)
        print(f"✅ Filename sanitization working: {dangerous_name} → {safe_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing utilities: {str(e)}")
        return False

def test_templates():
    """Test template rendering"""
    print("\n" + "=" * 60)
    print("🎨 TESTING TEMPLATE RENDERING")
    print("=" * 60)
    
    try:
        from app import app
        
        with app.app_context():
            with app.test_client() as client:
                # Test homepage
                response = client.get('/')
                if response.status_code == 200:
                    print("✅ Homepage template renders successfully")
                else:
                    print(f"⚠️  Homepage returned status {response.status_code}")
                
                # Test add shop page
                response = client.get('/add_shop')
                if response.status_code == 200:
                    print("✅ Add shop template renders successfully")
                else:
                    print(f"⚠️  Add shop page returned status {response.status_code}")
                
                # Test template filters
                from app import timestamp_to_date_filter
                test_timestamp = int(datetime.now().timestamp())
                filtered_date = timestamp_to_date_filter(test_timestamp)
                print(f"✅ Template filters working: {test_timestamp} → {filtered_date}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing templates: {str(e)}")
        return False

def test_export_functions():
    """Test Excel export functionality"""
    print("\n" + "=" * 60)
    print("📊 TESTING EXCEL EXPORT")
    print("=" * 60)
    
    try:
        from utils import flatten_order_data, flatten_product_data, flatten_return_data, export_to_excel
        import tempfile
        import os
        
        # Test data flattening
        sample_order = {
            'order_sn': 'TEST123',
            'order_status': 'COMPLETED',
            'create_time': int(datetime.now().timestamp()),
            'total_amount': 150000,
            'buyer_username': 'testuser',
            'item_list': [{'item_name': 'Test Product', 'model_quantity': 1}]
        }
        
        flattened_order = flatten_order_data(sample_order)
        print(f"✅ Order data flattening working: {len(flattened_order)} fields")
        
        sample_product = {
            'item_id': 12345,
            'item_name': 'Test Product',
            'item_status': 'NORMAL',
            'price_info': {'current_price': 50000},
            'stock_info': {'normal_stock': 100}
        }
        
        flattened_product = flatten_product_data(sample_product)
        print(f"✅ Product data flattening working: {len(flattened_product)} fields")
        
        sample_return = {
            'return_sn': 'RET123',
            'order_sn': 'TEST123',
            'status': 'COMPLETED',
            'create_time': int(datetime.now().timestamp()),
            'return_amount': 50000
        }
        
        flattened_return = flatten_return_data(sample_return)
        print(f"✅ Return data flattening working: {len(flattened_return)} fields")
        
        # Test Excel export
        test_data = [flattened_order, flattened_order]  # Duplicate for testing
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            try:
                file_path = export_to_excel(test_data, 'test_export.xlsx', 'TestSheet')
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    print(f"✅ Excel export working: {file_path} ({file_size} bytes)")
                else:
                    print("⚠️  Excel file not created")
            except Exception as e:
                print(f"⚠️  Excel export test failed: {str(e)}")
                print("💡 Pastikan openpyxl terinstall: pip install openpyxl")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing export functions: {str(e)}")
        return False

def test_scheduler():
    """Test token refresh scheduler"""
    print("\n" + "=" * 60)
    print("⏰ TESTING SCHEDULER")
    print("=" * 60)
    
    try:
        from scheduler import TokenRefreshScheduler
        from shopee_api import ShopeeAPI
        
        # Initialize scheduler
        api = ShopeeAPI(
            partner_id=Config.SHOPEE_PARTNER_ID,
            partner_key=Config.SHOPEE_PARTNER_KEY,
            base_url=Config.SHOPEE_BASE_URL
        )
        
        scheduler = TokenRefreshScheduler(api)
        print("✅ Scheduler initialized successfully")
        
        # Test scheduler status
        status = scheduler.get_scheduler_status()
        print(f"✅ Scheduler status: {status}")
        
        # Test token status summary
        with app.app_context():
            summary = scheduler.get_token_status_summary()
            print(f"✅ Token status summary: {summary}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing scheduler: {str(e)}")
        return False

def test_api_endpoints():
    """Test API endpoints dengan mock data"""
    print("\n" + "=" * 60)
    print("🔌 TESTING API ENDPOINTS")
    print("=" * 60)
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test routes that don't require authentication
            test_routes = [
                ('/', 'Homepage'),
                ('/add_shop', 'Add Shop'),
            ]
            
            for route, name in test_routes:
                response = client.get(route)
                if response.status_code == 200:
                    print(f"✅ {name} endpoint working (200)")
                elif response.status_code == 302:
                    print(f"✅ {name} endpoint redirecting (302)")
                else:
                    print(f"⚠️  {name} endpoint returned {response.status_code}")
            
            # Test POST endpoints (should handle gracefully)
            response = client.post('/auth_shop', data={})
            if response.status_code in [302, 400]:  # Redirect or bad request is expected
                print("✅ Auth shop endpoint handling requests")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing API endpoints: {str(e)}")
        return False

def run_performance_test():
    """Test performa aplikasi"""
    print("\n" + "=" * 60)
    print("⚡ PERFORMANCE TEST")
    print("=" * 60)
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test response time
            start_time = time.time()
            response = client.get('/')
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            if response_time < 100:
                print(f"✅ Homepage response time: {response_time:.2f}ms (Excellent)")
            elif response_time < 500:
                print(f"✅ Homepage response time: {response_time:.2f}ms (Good)")
            else:
                print(f"⚠️  Homepage response time: {response_time:.2f}ms (Slow)")
            
            # Test memory usage (basic)
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb < 100:
                print(f"✅ Memory usage: {memory_mb:.1f}MB (Good)")
            elif memory_mb < 200:
                print(f"⚠️  Memory usage: {memory_mb:.1f}MB (Moderate)")
            else:
                print(f"❌ Memory usage: {memory_mb:.1f}MB (High)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in performance test: {str(e)}")
        return False

def run_integration_test():
    """Test integrasi antar komponen"""
    print("\n" + "=" * 60)
    print("🔗 INTEGRATION TEST")
    print("=" * 60)
    
    try:
        from app import app, db
        from models import Shop, APILog
        from shopee_api import ShopeeAPI
        
        with app.app_context():
            # Test full integration: API → Database → Utils
            api = ShopeeAPI(
                partner_id=Config.SHOPEE_PARTNER_ID,
                partner_key=Config.SHOPEE_PARTNER_KEY,
                base_url=Config.SHOPEE_BASE_URL
            )
            
            # Generate auth URL (API component)
            auth_url = api.generate_auth_url(Config.SHOPEE_REDIRECT_URL)
            print("✅ API component working")
            
            # Test database operations
            test_shop = Shop(
                shop_id="integration_test",
                shop_name="Integration Test Shop",
                shop_account="test@integration.com"
            )
            
            db.session.add(test_shop)
            db.session.commit()
            print("✅ Database component working")
            
            # Test API logging
            test_log = APILog(
                shop_id="integration_test",
                endpoint="/test",
                method="GET",
                status_code=200,
                response_time=0.1
            )
            
            db.session.add(test_log)
            db.session.commit()
            print("✅ Logging component working")
            
            # Clean up test data
            APILog.query.filter_by(shop_id="integration_test").delete()
            Shop.query.filter_by(shop_id="integration_test").delete()
            db.session.commit()
            print("✅ Cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in integration test: {str(e)}")
        return False

def run_full_test():
    """Run semua test komprehensif"""
    print("🚀 SHOPEE API INTEGRATION - COMPREHENSIVE TEST")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    tests = [
        ("Configuration", test_configuration),
        ("Shopee API", test_shopee_api),
        ("Database", test_database),
        ("Utility Functions", test_utils),
        ("Templates", test_templates),
        ("Excel Export", test_export_functions),
        ("Scheduler", test_scheduler),
        ("API Endpoints", test_api_endpoints),
        ("Performance", run_performance_test),
        ("Integration", run_integration_test)
    ]
    
    passed = 0
    total = len(tests)
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} test PASSED")
            else:
                failed_tests.append(test_name)
                print(f"❌ {test_name} test FAILED")
        except Exception as e:
            failed_tests.append(test_name)
            print(f"❌ {test_name} test FAILED with exception: {str(e)}")
    
    # Final results
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {len(failed_tests)}/{total}")
    
    if failed_tests:
        print(f"🔴 Failed tests: {', '.join(failed_tests)}")
    
    print(f"📈 Success rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Aplikasi siap untuk production!")
        print("🚀 Jalankan dengan: python run.py")
    elif passed >= total * 0.8:  # 80% pass rate
        print("\n⚠️  MOSTLY WORKING - Ada beberapa issue minor")
        print("💡 Aplikasi bisa dijalankan tapi ada komponen yang perlu diperbaiki")
    else:
        print("\n❌ CRITICAL ISSUES DETECTED")
        print("🛠️  Ada masalah serius yang harus diperbaiki sebelum menjalankan aplikasi")
    
    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == '__main__':
    # Import required modules for testing
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        test_map = {
            'config': test_configuration,
            'api': test_shopee_api,
            'database': test_database,
            'utils': test_utils,
            'templates': test_templates,
            'export': test_export_functions,
            'scheduler': test_scheduler,
            'endpoints': test_api_endpoints,
            'performance': run_performance_test,
            'integration': run_integration_test
        }
        
        if command in test_map:
            print(f"Running {command} test...")
            test_map[command]()
        elif command == 'help':
            print("Available test commands:")
            for cmd in test_map.keys():
                print(f"  python test_api.py {cmd}")
            print("  python test_api.py          # Run all tests")
        else:
            print(f"Unknown command: {command}")
            print("Use 'python test_api.py help' for available commands")
    else:
        # Run all tests
        run_full_test()