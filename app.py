# -*- coding: utf-8 -*-
import os
import time
import hmac
import hashlib
import requests
import json
import threading
from flask import Flask, request, redirect, url_for, render_template, session, flash, make_response
from datetime import datetime, timedelta
import pandas as pd
import io

# Global variable to store export progress (thread-safe alternative to session)
export_progress_store = {}

# ==============================================================================
# KONFIGURASI WAJIB
# Ganti nilai-nilai di bawah ini dengan data Anda.
# ==============================================================================
# ID Partner dari Shopee Developer Center
PARTNER_ID = 2012002

# Kunci Partner dari Shopee Developer Center
PARTNER_KEY = "shpk715045424a75484f6b7379476f4c44444d506b4d4b6f7a6d4f544a4f6a6d"

# Domain tempat aplikasi Anda berjalan (tanpa / di akhir)
REDIRECT_URL_DOMAIN = "https://alvinnovendra2.pythonanywhere.com" 

# URL dasar API Shopee. Gunakan ini untuk PRODUKSI.
# Untuk Sandbox, ganti menjadi: "https://partner.test-stable.shopeemobile.com"
BASE_URL = "https://partner.shopeemobile.com"

# ==============================================================================
# INISIALISASI APLIKASI FLASK
# ==============================================================================
app = Flask(__name__)

# Kunci rahasia yang kuat untuk mengamankan session. Tidak perlu diubah.
app.config['SECRET_KEY'] = 'pbkdf2:sha256:600000$V8iLpGcE9aQzRkYw$9a8f3b1e2c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f'

# ==============================================================================
# FUNGSI HELPER UNTUK API SHOPEE
# ==============================================================================
def generate_signature(path, timestamp, access_token=None, shop_id=None):
    """Membuat signature untuk otentikasi panggilan API V2."""
    partner_id_str = str(PARTNER_ID)
    base_string_parts = [partner_id_str, path, str(timestamp)]
    if access_token:
        base_string_parts.append(access_token)
    if shop_id:
        base_string_parts.append(str(shop_id))
    
    base_string = "".join(base_string_parts)
    return hmac.new(PARTNER_KEY.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha256).hexdigest()

def call_shopee_api(path, method='POST', shop_id=None, access_token=None, body=None, max_retries=3):
    """Fungsi generik untuk memanggil semua endpoint Shopee API v2 dengan rate limiting dan retry."""
    timestamp = int(time.time())
    
    if not all([PARTNER_ID, PARTNER_KEY not in ["", "GANTI_DENGAN_PARTNER_KEY_ANDA"]]):
        msg = "Partner ID / Partner Key belum diatur di file konfigurasi."
        app.logger.error(msg)
        return None, msg

    sign = generate_signature(path, timestamp, access_token, shop_id)
    
    params = {"partner_id": PARTNER_ID, "timestamp": timestamp, "sign": sign}
    if access_token:
        params["access_token"] = access_token
    if shop_id:
        params["shop_id"] = shop_id

    full_url = f"{BASE_URL}{path}"
    headers = {'Content-Type': 'application/json'}

    # Retry mechanism with exponential backoff
    for attempt in range(max_retries):
        try:
            if method.upper() == 'POST':
                response = requests.post(full_url, params=params, json=body, headers=headers, timeout=30)
            else:
                response = requests.get(full_url, params={**params, **(body or {})}, headers=headers, timeout=30)
            
            # Handle HTTP 429 Too Many Requests
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                app.logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds. Attempt {attempt + 1}/{max_retries}")
                time.sleep(retry_after)
                continue
            
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("error"):
                error_msg = f"Shopee API Error: {response_data.get('message', 'Unknown error')} (Req ID: {response_data.get('request_id')})"
                app.logger.error(error_msg)
                return None, error_msg
                
            return response_data, None
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                error_msg = f"Kesalahan Jaringan: {e}"
                app.logger.error(error_msg)
                return None, error_msg
            else:
                # Exponential backoff: 1s, 2s, 4s
                backoff_time = 2 ** attempt
                app.logger.warning(f"Request failed, retrying in {backoff_time} seconds. Attempt {attempt + 1}/{max_retries}")
                time.sleep(backoff_time)
                continue
        except Exception as e:
            error_msg = f"Terjadi kesalahan tak terduga: {e}"
            app.logger.error(error_msg)
            return None, error_msg
    
    return None, "Max retries exceeded"

# ==============================================================================
# RUTE-RUTE (HALAMAN) APLIKASI
# ==============================================================================
@app.route('/')
def dashboard():
    """Menampilkan halaman utama dengan daftar toko dari session."""
    shops = session.get('shops', {})
    
    today = datetime.now()
    date_to_default = today.strftime('%Y-%m-%d')
    date_from_default = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    return render_template(
        'dashboard.html', 
        shops=shops, 
        date_from=date_from_default, 
        date_to=date_to_default
    )

@app.route('/authorize')
def authorize():
    """Mengarahkan pengguna ke halaman otorisasi Shopee."""
    path = "/api/v2/shop/auth_partner"
    sign = generate_signature(path, int(time.time()))
    redirect_full_url = f"{REDIRECT_URL_DOMAIN}{url_for('callback')}"
    
    auth_url = f"{BASE_URL}{path}?partner_id={PARTNER_ID}&redirect={redirect_full_url}&sign={sign}&timestamp={int(time.time())}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Menangani callback dari Shopee setelah otorisasi."""
    code = request.args.get('code')
    shop_id_str = request.args.get('shop_id')

    if not code or not shop_id_str:
        flash("Callback dari Shopee tidak valid.", 'danger')
        return redirect(url_for('dashboard'))

    path_token = "/api/v2/auth/token/get"
    body_token = {"code": code, "shop_id": int(shop_id_str)}
    token_data, error = call_shopee_api(path_token, body=body_token)

    if error:
        flash(f"Gagal mendapatkan token: {error}", 'danger')
        return redirect(url_for('dashboard'))

    access_token = token_data.get('access_token')
    if not access_token:
        flash("Respons token dari Shopee tidak lengkap.", 'danger')
        return redirect(url_for('dashboard'))

    # Get shop name using various methods
    shop_name = f"Toko {shop_id_str}"  # Default fallback
    
    # Method 1: Try get_shop_info
    try:
        path_info = "/api/v2/shop/get_shop_info"
        info_data, error = call_shopee_api(path_info, method='GET', shop_id=int(shop_id_str), access_token=access_token)
        
        app.logger.info(f"Shop info API response: {info_data}")
        app.logger.info(f"Shop info API error: {error}")
        
        if error:
            app.logger.warning(f"Method 1 failed - get_shop_info error: {error}")
        elif info_data and 'response' in info_data:
            response_data = info_data.get('response', {})
            app.logger.info(f"DEBUG: response_data keys: {list(response_data.keys())}")
            app.logger.info(f"DEBUG: shop_name value: '{response_data.get('shop_name')}'")
            app.logger.info(f"DEBUG: shop_name type: {type(response_data.get('shop_name'))}")
            
            extracted_shop_name = response_data.get('shop_name', '').strip()
            if extracted_shop_name:
                shop_name = extracted_shop_name
                app.logger.info(f"SUCCESS: Found shop name via get_shop_info: '{shop_name}'")
            else:
                app.logger.warning(f"Method 1 failed - no valid shop_name in response: {response_data}")
        else:
            app.logger.warning(f"Method 1 failed - no response data: {info_data}")
            
    except Exception as e:
        app.logger.error(f"Exception in get_shop_info: {e}")
    
    # Method 2: Try get_profile if first method failed
    if shop_name == f"Toko {shop_id_str}":
        try:
            profile_data, profile_error = call_shopee_api("/api/v2/shop/get_profile", method='GET', 
                                                        shop_id=int(shop_id_str), access_token=access_token)
            
            app.logger.info(f"Shop profile API response: {profile_data}")
            app.logger.info(f"Shop profile API error: {profile_error}")
            
            if not profile_error and profile_data and 'response' in profile_data:
                response_data = profile_data.get('response', {})
                extracted_shop_name = response_data.get('shop_name', '').strip()
                if extracted_shop_name:
                    shop_name = extracted_shop_name
                    app.logger.info(f"SUCCESS: Found shop name via get_profile: '{shop_name}'")
                    
        except Exception as e:
            app.logger.error(f"Exception in get_profile: {e}")
    
    # Final check
    if shop_name == f"Toko {shop_id_str}":
        flash(f"Tidak dapat mengambil nama toko. Menggunakan ID sebagai nama: {shop_name}", 'warning')
        app.logger.warning(f"FAILED: Could not retrieve shop name, using fallback: {shop_name}")
    else:
        app.logger.info(f"FINAL: Using shop name: {shop_name}")

    shops = session.get('shops', {})
    shops[shop_id_str] = {
        'shop_id': shop_id_str,
        'shop_name': shop_name,
        'access_token': access_token,
        'refresh_token': token_data.get('refresh_token'),
        'expire_in': int(time.time()) + token_data.get('expire_in', 14400)
    }
    session['shops'] = shops
    session.modified = True

    flash(f"Toko '{shop_name}' berhasil dihubungkan.", 'success')
    return redirect(url_for('dashboard'))
    
@app.route('/clear_session')
def clear_session():
    """Menghapus semua data dari session untuk memulai dari awal."""
    session.clear()
    flash('Semua data sesi dan toko terhubung telah dihapus.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/clear_temp_data')
def clear_temp_data():
    """Menghapus data sementara export (export_progress_store) tanpa menghapus session."""
    global export_progress_store
    
    # Count berapa data yang akan dihapus
    count_before = len(export_progress_store)
    
    # Clear semua data sementara
    export_progress_store.clear()
    
    flash(f'Data sementara berhasil dihapus ({count_before} export data dihapus dari memory).', 'success')
    app.logger.info(f"Manual cleanup: Cleared {count_before} export data from memory store")
    
    return redirect(url_for('dashboard'))

@app.route('/test_shop_info')
def test_shop_info():
    """Test shop info API to debug nama toko issue."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops connected"}
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    results = {}
    
    # Test berbagai endpoint untuk ambil nama toko
    endpoints_to_test = [
        "/api/v2/shop/get_shop_info",
        "/api/v2/shop/get_profile", 
        "/api/v2/public/get_shops_by_partner",
        "/api/v2/merchant/get_merchant_info"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            response, error = call_shopee_api(endpoint, method='GET', 
                                            shop_id=shop_id, access_token=access_token)
            
            results[endpoint] = {
                "response": response,
                "error": error,
                "shop_name_found": response.get('response', {}).get('shop_name') if response else None
            }
        except Exception as e:
            results[endpoint] = {"error": str(e)}
    
    # Test dengan body parameter juga
    try:
        body_test = {}
        response, error = call_shopee_api("/api/v2/shop/get_shop_info", method='GET', 
                                        shop_id=shop_id, access_token=access_token, body=body_test)
        results["get_shop_info_with_body"] = {
            "response": response,
            "error": error,
            "shop_name_found": response.get('response', {}).get('shop_name') if response else None
        }
    except Exception as e:
        results["get_shop_info_with_body"] = {"error": str(e)}
    
    return results

@app.route('/test_date_filter_specific_shop')
def test_date_filter_specific_shop():
    """Test apakah date filtering berfungsi dengan return spesifik di shop tertentu."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops connected"}
    
    # Test dengan shop_id 59414059 untuk mencari return 2501010C4UCUTPB
    target_shop_id = "59414059"
    target_return_sn = "2501010C4UCUTPB"
    
    # Debug: Show all connected shops
    connected_shops = {shop_id: shop_data.get('shop_name', 'Unknown') for shop_id, shop_data in shops.items()}
    
    if target_shop_id not in shops:
        return {
            "error": f"Shop {target_shop_id} not connected. Please authorize it first.",
            "connected_shops": connected_shops,
            "note": "You need to connect shop 59414059 via /authorize first"
        }
    
    shop_data = shops[target_shop_id]
    access_token = shop_data['access_token']
    
    results = {}
    
    # Test 1: Filter tanggal 1 Januari 2025 (tanggal return dibuat)
    try:
        from datetime import datetime, timedelta
        target_date = datetime(2025, 1, 1)  # 1 Januari 2025
        start_date = target_date.replace(hour=0, minute=0, second=0)
        end_date = target_date.replace(hour=23, minute=59, second=59)
        
        filter_body = {
            "page_no": 1, 
            "page_size": 20,
            "create_time_from": int(start_date.timestamp()),
            "create_time_to": int(end_date.timestamp())
        }
        
        filter_response, filter_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                      shop_id=target_shop_id, access_token=access_token, body=filter_body)
        
        if filter_response and not filter_error:
            returns_filtered = filter_response.get('response', {}).get('return', [])
            found_target = any(ret.get('return_sn') == target_return_sn for ret in returns_filtered)
            
            results["jan_1_2025_filter"] = {
                "filter_range": f"{start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}",
                "total_returns": len(returns_filtered),
                "target_return_found": found_target,
                "return_sns_found": [ret.get('return_sn') for ret in returns_filtered],
                "error": None
            }
        else:
            results["jan_1_2025_filter"] = {
                "error": filter_error,
                "filter_range": f"{start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}"
            }
    except Exception as e:
        results["jan_1_2025_filter"] = {"error": str(e)}
    
    # Test 2: Filter tanggal yang lebih luas (Desember 2024 - Januari 2025)
    try:
        wide_start = datetime(2024, 12, 1)
        wide_end = datetime(2025, 1, 31, 23, 59, 59)
        
        wide_filter_body = {
            "page_no": 1, 
            "page_size": 50,
            "create_time_from": int(wide_start.timestamp()),
            "create_time_to": int(wide_end.timestamp())
        }
        
        wide_response, wide_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                   shop_id=target_shop_id, access_token=access_token, body=wide_filter_body)
        
        if wide_response and not wide_error:
            wide_returns = wide_response.get('response', {}).get('return', [])
            found_target_wide = any(ret.get('return_sn') == target_return_sn for ret in wide_returns)
            
            results["wide_filter_dec2024_jan2025"] = {
                "filter_range": f"{wide_start.strftime('%Y-%m-%d')} to {wide_end.strftime('%Y-%m-%d')}",
                "total_returns": len(wide_returns),
                "target_return_found": found_target_wide,
                "return_sns_found": [ret.get('return_sn') for ret in wide_returns],
                "error": None
            }
        else:
            results["wide_filter_dec2024_jan2025"] = {
                "error": wide_error,
                "filter_range": f"{wide_start.strftime('%Y-%m-%d')} to {wide_end.strftime('%Y-%m-%d')}"
            }
    except Exception as e:
        results["wide_filter_dec2024_jan2025"] = {"error": str(e)}
    
    # Test 3: Get return detail to check status and understand why it doesn't appear in list
    try:
        detail_body = {"return_sn": target_return_sn}
        detail_response, detail_error = call_shopee_api("/api/v2/returns/get_return_detail", method='GET', 
                                                       shop_id=target_shop_id, access_token=access_token, body=detail_body)
        
        if detail_response and not detail_error:
            return_detail = detail_response.get('response', {})
            results["return_detail_analysis"] = {
                "status": return_detail.get('status'),
                "reason": return_detail.get('reason'),
                "needs_logistics": return_detail.get('needs_logistics'),
                "logistics_status": return_detail.get('logistics_status'),
                "negotiation_status": return_detail.get('negotiation', {}).get('negotiation_status'),
                "seller_proof_status": return_detail.get('seller_proof', {}).get('seller_proof_status'),
                "return_refund_type": return_detail.get('return_refund_type'),
                "return_solution": return_detail.get('return_solution'),
                "create_time": return_detail.get('create_time'),
                "create_time_readable": datetime.fromtimestamp(return_detail.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if return_detail.get('create_time') else None,
                "note": "Return details - checking why it doesn't appear in get_return_list"
            }
        else:
            results["return_detail_analysis"] = {"error": detail_error}
    except Exception as e:
        results["return_detail_analysis"] = {"error": str(e)}
    
    # Test 4: Try with status filter to see if ACCEPTED returns show up
    try:
        status_filter_body = {
            "page_no": 1, 
            "page_size": 20,
            "create_time_from": int(datetime(2025, 1, 1).timestamp()),
            "create_time_to": int(datetime(2025, 1, 2).timestamp()),
            "status": "ACCEPTED"
        }
        
        status_response, status_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                       shop_id=target_shop_id, access_token=access_token, body=status_filter_body)
        
        if status_response and not status_error:
            status_returns = status_response.get('response', {}).get('return', [])
            found_with_status = any(ret.get('return_sn') == target_return_sn for ret in status_returns)
            
            results["status_filter_test"] = {
                "filter_used": "status=ACCEPTED + date filter",
                "total_returns": len(status_returns),
                "target_return_found": found_with_status,
                "return_sns_found": [ret.get('return_sn') for ret in status_returns],
                "error": None
            }
        else:
            results["status_filter_test"] = {"error": status_error}
    except Exception as e:
        results["status_filter_test"] = {"error": str(e)}
    
    # Test 5: Try without any filters (just pagination) to see if return exists at all
    try:
        no_filter_body = {
            "page_no": 1, 
            "page_size": 50
        }
        
        no_filter_response, no_filter_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                             shop_id=target_shop_id, access_token=access_token, body=no_filter_body)
        
        if no_filter_response and not no_filter_error:
            all_returns = no_filter_response.get('response', {}).get('return', [])
            found_no_filter = any(ret.get('return_sn') == target_return_sn for ret in all_returns)
            
            results["no_filter_test"] = {
                "filter_used": "No filters (just pagination)",
                "total_returns": len(all_returns),
                "target_return_found": found_no_filter,
                "return_sns_sample": [ret.get('return_sn') for ret in all_returns[:5]],
                "error": None
            }
        else:
            results["no_filter_test"] = {"error": no_filter_error}
    except Exception as e:
        results["no_filter_test"] = {"error": str(e)}
    
    return {
        "shop_id": target_shop_id,
        "shop_name": shops[target_shop_id].get('shop_name', 'Unknown'),
        "connected_shops": connected_shops,
        "target_return_sn": target_return_sn,
        "expected_date": "2025-01-01 07:58:52",
        "test_results": results,
        "note": "Testing if return 2501010C4UCUTPB appears in get_return_list with correct date filter",
        "conclusion": "Return accessible via get_return_detail but NOT in get_return_list - API inconsistency detected"
    }

@app.route('/test_date_filter')
def test_date_filter():
    """Test apakah date filtering berfungsi dengan benar pada returns API."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops connected"}
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    results = {}
    
    # Test 1: Tanpa filter (ambil semua data)
    try:
        no_filter_body = {"page_no": 1, "page_size": 5}
        no_filter_response, no_filter_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                            shop_id=shop_id, access_token=access_token, body=no_filter_body)
        
        returns_no_filter = no_filter_response.get('response', {}).get('return_list', []) if no_filter_response else []
        results["no_filter"] = {
            "total_returns": len(returns_no_filter),
            "sample_dates": [
                {
                    "return_sn": item.get('return_sn'),
                    "create_time": item.get('create_time'),
                    "create_date": datetime.fromtimestamp(item.get('create_time')).strftime('%Y-%m-%d') if item.get('create_time') else None
                } for item in returns_no_filter[:3]
            ],
            "error": no_filter_error
        }
    except Exception as e:
        results["no_filter"] = {"error": str(e)}
    
    # Test 2: Dengan filter 7 hari terakhir
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        filter_body = {
            "page_no": 1, 
            "page_size": 5,
            "create_time_from": int(start_date.timestamp()),
            "create_time_to": int(end_date.timestamp())
        }
        
        filter_response, filter_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                      shop_id=shop_id, access_token=access_token, body=filter_body)
        
        returns_filtered = filter_response.get('response', {}).get('return_list', []) if filter_response else []
        results["with_filter_7days"] = {
            "filter_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_returns": len(returns_filtered),
            "sample_dates": [
                {
                    "return_sn": item.get('return_sn'),
                    "create_time": item.get('create_time'),
                    "create_date": datetime.fromtimestamp(item.get('create_time')).strftime('%Y-%m-%d') if item.get('create_time') else None
                } for item in returns_filtered[:3]
            ],
            "error": filter_error
        }
    except Exception as e:
        results["with_filter_7days"] = {"error": str(e)}
    
    # Test 3: Filter yang sangat spesifik (kemarin saja)
    try:
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        specific_filter_body = {
            "page_no": 1, 
            "page_size": 10,
            "create_time_from": int(yesterday_start.timestamp()),
            "create_time_to": int(yesterday_end.timestamp())
        }
        
        specific_response, specific_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                          shop_id=shop_id, access_token=access_token, body=specific_filter_body)
        
        returns_specific = specific_response.get('response', {}).get('return_list', []) if specific_response else []
        results["yesterday_only"] = {
            "filter_range": f"{yesterday_start.strftime('%Y-%m-%d %H:%M')} to {yesterday_end.strftime('%Y-%m-%d %H:%M')}",
            "total_returns": len(returns_specific),
            "sample_dates": [
                {
                    "return_sn": item.get('return_sn'),
                    "create_time": item.get('create_time'),
                    "create_date": datetime.fromtimestamp(item.get('create_time')).strftime('%Y-%m-%d %H:%M') if item.get('create_time') else None
                } for item in returns_specific
            ],
            "error": specific_error
        }
    except Exception as e:
        results["yesterday_only"] = {"error": str(e)}
    
    return results

@app.route('/test_returns_api')
def test_returns_api():
    """Test returns API to debug issues and see available fields."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    # Test single API call
    return_body = {"page_no": 1, "page_size": 2}
    response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                    shop_id=shop_id, access_token=access_token, body=return_body)
    
    # Also test return detail API for more fields
    return_detail_response = None
    return_detail_error = None
    if response and not error:
        return_list = response.get('response', {}).get('return', [])
        if return_list:
            return_sn = return_list[0].get('return_sn')
            if return_sn:
                detail_body = {"return_sn_list": [return_sn]}
                return_detail_response, return_detail_error = call_shopee_api("/api/v2/returns/get_return_detail", method='GET', 
                                                                           shop_id=shop_id, access_token=access_token, body=detail_body)
    
    return {
        "shop_id": shop_id,
        "returns_list_response": response,
        "returns_list_error": error,
        "returns_detail_response": return_detail_response,
        "returns_detail_error": return_detail_error,
        "url_called": f"{BASE_URL}/api/v2/returns/get_return_list"
    }

@app.route('/test_real_tracking_api')
def test_real_tracking_api():
    """Test to find actual SPX tracking numbers that can be tracked on SPX website."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    # Test order SNs - focus on finding real tracking numbers
    test_orders = [
        "250426A7B1H300",
        "250406HNTVAXTC", 
        "250426A72EV9TV",
        "250422VSVX309M",
        "2504256KHEKDY2"
    ]
    
    results = {}
    
    for order_sn in test_orders:
        print(f"Testing tracking for order: {order_sn}")
        order_result = {}
        
        try:
            # Method 1: Get logistics tracking info - cari di description
            logistics_params = {"order_sn": order_sn}
            logistics_response, logistics_error = call_shopee_api("/api/v2/logistics/get_tracking_info", method='GET', 
                                                                shop_id=shop_id, access_token=access_token, body=logistics_params)
            
            extracted_tracking = []
            if logistics_response and not logistics_error:
                tracking_info = logistics_response.get('response', {}).get('tracking_info', [])
                
                # Scan descriptions for tracking number patterns
                for info in tracking_info:
                    description = info.get('description', '')
                    
                    # Look for SPX tracking patterns in description
                    import re
                    # SPX patterns: SPXID123456789, ID123456789000, etc
                    spx_patterns = [
                        r'SPXID\d+',           # SPXID followed by digits
                        r'ID\d{10,15}',        # ID followed by 10-15 digits  
                        r'SPX\d{10,15}',       # SPX followed by digits
                        r'\b\d{10,15}ID\b',    # 10-15 digits followed by ID
                        r'resi[:\s]+([A-Z0-9]{10,20})',  # "resi: ABC123456"
                        r'tracking[:\s]+([A-Z0-9]{10,20})',  # "tracking: ABC123456"
                        r'awb[:\s]+([A-Z0-9]{10,20})'   # "awb: ABC123456"
                    ]
                    
                    for pattern in spx_patterns:
                        matches = re.findall(pattern, description, re.IGNORECASE)
                        if matches:
                            extracted_tracking.extend(matches)
                
                order_result["logistics_tracking"] = {
                    "total_updates": len(tracking_info),
                    "extracted_numbers": list(set(extracted_tracking)),  # Remove duplicates
                    "logistics_status": logistics_response.get('response', {}).get('logistics_status', ''),
                    "sample_descriptions": [info.get('description', '')[:100] for info in tracking_info[:3]]
                }
            
            # Method 2: Alternative logistics endpoints
            # Try get_tracking_number endpoint
            tracking_params = {"order_sn": order_sn}
            tracking_response, tracking_error = call_shopee_api("/api/v2/logistics/get_tracking_number", method='GET', 
                                                              shop_id=shop_id, access_token=access_token, body=tracking_params)
            
            if tracking_response and not tracking_error:
                order_result["tracking_number_api"] = tracking_response.get('response', {})
            else:
                order_result["tracking_number_api"] = {"error": tracking_error}
            
            results[order_sn] = order_result
            
        except Exception as e:
            results[order_sn] = {"error": str(e)}
        
        # Rate limiting
        import time
        time.sleep(0.3)
    
    return {
        "shop_id": shop_id,
        "tracking_analysis": results,
        "note": "Looking for real SPX tracking numbers that can be tracked on SPX website"
    }

@app.route('/test_logistics_api')
def test_logistics_api():
    """Test logistics API to get tracking number."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    # First get a return to get order_sn
    return_body = {"page_no": 1, "page_size": 1}
    returns_response, returns_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                    shop_id=shop_id, access_token=access_token, body=return_body)
    
    if returns_error or not returns_response:
        return {"error": f"Failed to get returns: {returns_error}"}
    
    return_list = returns_response.get('response', {}).get('return', [])
    if not return_list:
        return {"error": "No returns found to test with"}
    
    order_sn = return_list[0].get('order_sn')
    if not order_sn:
        return {"error": "No order_sn found in return"}
    
    # Test logistics APIs with correct parameters
    results = {}
    
    # Try 1: logistics tracking with order_sn (not order_sn_list)
    tracking_body1 = {"order_sn": order_sn}
    tracking_response1, tracking_error1 = call_shopee_api("/api/v2/logistics/get_tracking_number", method='GET', 
                                                        shop_id=shop_id, access_token=access_token, body=tracking_body1)
    results["logistics_tracking_single"] = {"response": tracking_response1, "error": tracking_error1}
    
    # Try 2: get_shipping_parameter (different endpoint)
    shipping_body2 = {"order_sn": order_sn}
    shipping_response2, shipping_error2 = call_shopee_api("/api/v2/logistics/get_shipping_parameter", method='GET', 
                                                        shop_id=shop_id, access_token=access_token, body=shipping_body2)
    results["shipping_parameter"] = {"response": shipping_response2, "error": shipping_error2}
    
    # Try 3: get_order_logistics (alternative)
    logistics_body3 = {"order_sn": order_sn}
    logistics_response3, logistics_error3 = call_shopee_api("/api/v2/logistics/get_order_logistics", method='GET', 
                                                          shop_id=shop_id, access_token=access_token, body=logistics_body3)
    results["order_logistics"] = {"response": logistics_response3, "error": logistics_error3}
    
    return {
        "shop_id": shop_id,
        "order_sn": order_sn,
        "logistics_tests": results
    }

@app.route('/test_order_detail_api')
def test_order_detail_api():
    """Test order detail API to check payment method fields."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    # Test new batch of order SNs provided by user
    test_order_sns = [
        "250426A7B1H300",
        "250406HNTVAXTC", 
        "250426A72EV9TV",
        "250422VSVX309M",
        "2504256KHEKDY2",
        "250426A20MBDHG",
        "2504269X2BQ11V",
        "250427C5GTG0B4",
        "2504258DTXS4P6"
    ]
    
    # Remove duplicates and keep order
    unique_order_sns = []
    for sn in test_order_sns:
        if sn not in unique_order_sns:
            unique_order_sns.append(sn)
    
    # Test each order comprehensively  
    analysis_results = {}  # Initialize analysis_results
    
    for order_sn in unique_order_sns[:5]:  # Test first 5 orders to avoid timeout
        print(f"Analyzing order: {order_sn}")
        order_analysis = {}
        
        try:
            # Test 1: Enhanced order detail with package_list
            enhanced_params = {
                "order_sn_list": order_sn,
                "response_optional_fields": "package_list,shipping_carrier,logistics_status"
            }
            enhanced_response, enhanced_error = call_shopee_api("/api/v2/order/get_order_detail", method='GET', 
                                                              shop_id=shop_id, access_token=access_token, body=enhanced_params)
            
            # Test 2: Logistics tracking info
            logistics_params = {"order_sn": order_sn}
            logistics_response, logistics_error = call_shopee_api("/api/v2/logistics/get_tracking_info", method='GET', 
                                                                shop_id=shop_id, access_token=access_token, body=logistics_params)
            
            # Analyze results
            if enhanced_response and not enhanced_error:
                order_list = enhanced_response.get('response', {}).get('order_list', [])
                if order_list:
                    order = order_list[0]
                    
                    # Extract package info
                    packages = order.get('package_list', [])
                    package_info = []
                    for pkg in packages:
                        package_info.append({
                            "package_number": pkg.get('package_number', ''),
                            "shipping_carrier": pkg.get('shipping_carrier', ''),
                            "logistics_status": pkg.get('logistics_status', ''),
                            "logistics_channel_id": pkg.get('logistics_channel_id', '')
                        })
                    
                    order_analysis["order_detail"] = {
                        "order_sn": order.get('order_sn'),
                        "order_status": order.get('order_status'),
                        "booking_sn": order.get('booking_sn', ''),
                        "shipping_carrier": order.get('shipping_carrier', ''),
                        "package_count": len(packages),
                        "packages": package_info
                    }
            
            # Analyze logistics tracking
            if logistics_response and not logistics_error:
                logistics_data = logistics_response.get('response', {})
                tracking_info = logistics_data.get('tracking_info', [])
                
                order_analysis["logistics"] = {
                    "logistics_status": logistics_data.get('logistics_status', ''),
                    "tracking_updates": len(tracking_info),
                    "latest_status": tracking_info[0].get('logistics_status') if tracking_info else None,
                    "latest_description": tracking_info[0].get('description') if tracking_info else None
                }
            
            # Summary for this order
            has_package_number = any(pkg.get('package_number') for pkg in order_analysis.get('order_detail', {}).get('packages', []))
            has_tracking_history = order_analysis.get('logistics', {}).get('tracking_updates', 0) > 0
            
            order_analysis["summary"] = {
                "has_package_number": has_package_number,
                "has_tracking_history": has_tracking_history,
                "best_tracking_reference": ""
            }
            
            # Determine best tracking reference
            if has_package_number:
                first_package = order_analysis.get('order_detail', {}).get('packages', [{}])[0]
                order_analysis["summary"]["best_tracking_reference"] = first_package.get('package_number', '')
            elif order_analysis.get('order_detail', {}).get('booking_sn'):
                order_analysis["summary"]["best_tracking_reference"] = order_analysis.get('order_detail', {}).get('booking_sn')
            else:
                order_analysis["summary"]["best_tracking_reference"] = "No tracking available"
            
            analysis_results[order_sn] = order_analysis
            
        except Exception as e:
            print(f"Error analyzing order {order_sn}: {e}")
            analysis_results[order_sn] = {
                "error": str(e),
                "summary": {
                    "has_package_number": False,
                    "has_tracking_history": False,
                    "best_tracking_reference": "Error occurred"
                }
            }
        
        # Delay to avoid rate limiting
        import time
        time.sleep(0.2)
    
    # Overall summary
    total_orders = len(analysis_results)
    orders_with_package = len([r for r in analysis_results.values() if r.get('summary', {}).get('has_package_number')])
    orders_with_tracking = len([r for r in analysis_results.values() if r.get('summary', {}).get('has_tracking_history')])
    
    # Avoid division by zero
    if total_orders > 0:
        success_percentage = round(orders_with_package/total_orders*100, 1)
        success_rate = f"{orders_with_package}/{total_orders} ({success_percentage}% have package numbers)"
    else:
        success_rate = "0/0 (No orders analyzed)"
    
    overall_summary = {
        "total_analyzed": total_orders,
        "with_package_number": orders_with_package,
        "with_tracking_history": orders_with_tracking,
        "success_rate": success_rate
    }
    
    return {
        "shop_id": shop_id,
        "overall_summary": overall_summary,
        "order_analysis": analysis_results,
        "all_test_orders": unique_order_sns
    }

@app.route('/test_return_detail')
def test_return_detail():
    """Test get_return_detail API for specific return number to analyze date fields."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Allow testing with specific shop_id if provided in URL parameter
    target_shop_id = request.args.get('shop_id')
    
    if target_shop_id and target_shop_id in shops:
        # Use specified shop
        shop_id = target_shop_id
        shop_data = shops[shop_id]
        access_token = shop_data['access_token']
    else:
        # Get first shop for testing (default behavior)
        shop_id, shop_data = next(iter(shops.items()))
        access_token = shop_data['access_token']
    
    # First get a valid return_sn from existing returns to test the API format
    try:
        # Get actual return data from the shop first
        return_list_body = {"page_no": 1, "page_size": 5}
        list_response, list_error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                                  shop_id=shop_id, access_token=access_token, body=return_list_body)
        
        valid_return_sns = []
        if not list_error and list_response:
            returns = list_response.get('response', {}).get('return', [])
            valid_return_sns = [ret.get('return_sn') for ret in returns if ret.get('return_sn')]
        
        # Test both the requested return_sn and a valid one from the list
        test_return_sns = ["2501010C4UCUTPB"]  # User requested
        if valid_return_sns:
            test_return_sns.extend(valid_return_sns[:2])  # Add 2 valid ones for comparison
        
        results = {}
        
        for return_sn in test_return_sns:
            result_key = f"test_{return_sn}"
            
            # Try different parameter formats for each return_sn
            formats_to_try = [
                {"return_sn": return_sn},  # Documentation format
                {"return_sn_list": [return_sn]},  # Array format (in case docs are wrong)
                # Try as URL parameter instead of body (some APIs work this way)
            ]
            
            format_results = {}
            
            for i, format_body in enumerate(formats_to_try):
                try:
                    response, error = call_shopee_api("/api/v2/returns/get_return_detail", method='GET', 
                                                    shop_id=shop_id, access_token=access_token, body=format_body)
                    
                    format_results[f"format_{i+1}"] = {
                        "parameters": format_body,
                        "error": error,
                        "success": not bool(error),
                        "response_preview": {
                            "has_response": bool(response and response.get('response')),
                            "return_sn_in_response": response.get('response', {}).get('return_sn') if response else None
                        } if not error else None
                    }
                    
                    # If successful, extract date fields
                    if not error and response and response.get('response'):
                        return_detail = response.get('response', {})
                        date_fields = {}
                        
                        for key, value in return_detail.items():
                            if any(date_word in key.lower() for date_word in ['time', 'date', 'due']) and isinstance(value, (int, float)):
                                try:
                                    readable_date = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
                                    date_fields[key] = {
                                        "timestamp": value,
                                        "readable_date": readable_date
                                    }
                                except (ValueError, OSError):
                                    date_fields[key] = {
                                        "timestamp": value,
                                        "readable_date": "Invalid timestamp"
                                    }
                        
                        format_results[f"format_{i+1}"]["date_fields"] = date_fields
                        format_results[f"format_{i+1}"]["all_fields"] = list(return_detail.keys())
                    
                except Exception as e:
                    format_results[f"format_{i+1}"] = {
                        "parameters": format_body,
                        "exception": str(e)
                    }
                
                # Small delay between requests
                time.sleep(0.3)
            
            results[result_key] = format_results
        
        return {
            "shop_id": shop_id,
            "api_endpoint": "/api/v2/returns/get_return_detail",
            "valid_return_sns_found": valid_return_sns,
            "test_results": results,
            "note": "Testing multiple formats and return numbers to find working combination",
            "usage": "Add ?shop_id=59414059 to URL to test with specific shop"
        }
        
    except Exception as e:
        return {
            "shop_id": shop_id,
            "error": f"Exception in test setup: {str(e)}",
            "api_endpoint": "/api/v2/returns/get_return_detail"
        }

@app.route('/test_connection', methods=['GET', 'POST'])
def test_connection():
    """Test if server can receive requests."""
    print("=== TEST_CONNECTION CALLED ===")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    
    if request.method == 'POST':
        print(f"POST data: {request.get_json()}")
        return {"message": "POST request received successfully", "method": "POST"}
    else:
        return {"message": "GET request received successfully", "method": "GET"}

# Placeholder untuk fungsi lihat data
@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    flash("Fungsi 'Lihat Data' belum diimplementasikan. Gunakan tombol 'Export Excel'.", 'info')
    return redirect(url_for('dashboard'))

# ==============================================================================
# FUNGSI EXPORT DATA (IMPLEMENTASI BARU)
# ==============================================================================
@app.route('/export', methods=['POST'])
def export_data():
    """
    Initiates chunked export process and redirects to progress page.
    """
    shop_id = request.form.get('shop_id')
    data_type = request.form.get('data_type')
    date_from_str = request.form.get('date_from', '')
    date_to_str = request.form.get('date_to', '')
    # Single mode: manual date filter that includes RRBOC
    
    shop_data = session.get('shops', {}).get(shop_id)
    if not shop_data:
        flash(f"Toko dengan ID {shop_id} tidak ditemukan di sesi ini.", 'danger')
        return redirect(url_for('dashboard'))
    
    # Initialize progress tracking in global store and session
    export_id = f"{shop_id}_{data_type}_manual_filter_{int(time.time())}"
    export_data = {
        'export_id': export_id,
        'shop_id': shop_id,
        'data_type': data_type,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'status': 'initializing',
        'progress': 0,
        'total_estimated': 0,
        'current_step': 'Memulai ekspor...',
        'data': [],
        'error': None
    }
    
    # Store in both global store and session
    export_progress_store[export_id] = export_data
    session['current_export'] = export_data
    session.modified = True
    
    return redirect(url_for('export_progress'))

@app.route('/export_progress')
def export_progress():
    """Progress page for chunked export processing."""
    print("=== EXPORT_PROGRESS PAGE ACCESSED ===")
    export_data = session.get('current_export')
    print(f"Export data: {export_data}")
    
    if not export_data:
        print("No export data found, redirecting to dashboard")
        flash("Tidak ada proses ekspor yang sedang berjalan.", 'warning')
        return redirect(url_for('dashboard'))
    
    print("Rendering progress.html template")
    return render_template('progress.html', export_data=export_data)

@app.route('/api/progress_status')
def progress_status():
    """API endpoint to get current progress status."""
    print("=== PROGRESS_STATUS API CALLED ===")
    export_data = session.get('current_export')
    print(f"Progress status export_data: {export_data}")
    
    if not export_data:
        print("No export data found for progress status")
        return {"error": "No export process found"}, 404
    
    # Get updated data from global store
    export_id = export_data.get('export_id')
    if export_id and export_id in export_progress_store:
        export_data = export_progress_store[export_id]
        # Update session with latest data (WITHOUT the data field to reduce cookie size)
        session_data = export_data.copy()
        session_data.pop('data', None)  # Remove data from session to fix cookie size
        session['current_export'] = session_data
        session.modified = True
        # Safe print untuk data besar
        data_count = len(export_data.get('data', []))
        print(f"Using updated data from global store: Progress={export_data.get('progress')}%, Status={export_data.get('status')}, Records={data_count}")
    
    response_data = {
        "status": export_data.get('status', 'unknown'),
        "progress": export_data.get('progress', 0),
        "current_step": export_data.get('current_step', ''),
        "error": export_data.get('error'),
        "data_count": len(export_data.get('data', []))
    }
    print(f"Returning progress status: Progress={response_data['progress']}%, Status={response_data['status']}, Records={response_data['data_count']}")
    return response_data

@app.route('/start_chunked_export', methods=['POST'])
def start_chunked_export():
    """Start the actual chunked export process (SYNC VERSION for debugging)."""
    print("=== START_CHUNKED_EXPORT CALLED ===")
    app.logger.info("=== START_CHUNKED_EXPORT CALLED ===")
    
    export_data = session.get('current_export')
    print(f"Export data from session: {export_data}")
    app.logger.info(f"Export data from session: {export_data}")
    
    if not export_data:
        print("ERROR: No export process found")
        app.logger.error("ERROR: No export process found")
        return {"error": "No export process found"}, 400
    
    if export_data.get('status') == 'processing':
        print("Already processing, returning existing progress")
        app.logger.info("Already processing, returning existing progress")
        return {"status": "already_processing", "progress": export_data.get('progress', 0)}
    
    try:
        shop_data = session.get('shops', {}).get(export_data['shop_id'])
        print(f"Shop data found: {shop_data is not None}")
        app.logger.info(f"Shop data found: {shop_data is not None}")
        
        if not shop_data:
            print("ERROR: Shop data not found")
            app.logger.error("ERROR: Shop data not found")
            export_data['error'] = "Shop data not found"
            export_data['status'] = 'error'
            session.modified = True
            return {"error": "Shop data not found"}
            
        access_token = shop_data['access_token']
        print(f"Access token available: {access_token is not None}")
        app.logger.info(f"Access token available: {access_token is not None}")
        
        # Start async processing to prevent timeout
        export_data['status'] = 'processing'
        export_data['progress'] = 1.0
        export_data['current_step'] = 'Memulai proses export...'
        session.modified = True
        
        print(f"Starting async export for data_type: {export_data['data_type']}")
        app.logger.info(f"Starting async export for data_type: {export_data['data_type']}")
        
        # Start processing in background thread using global store
        def background_process():
            try:
                export_id = export_data.get('export_id')
                if not export_id or export_id not in export_progress_store:
                    return
                
                current_export = export_progress_store[export_id]
                
                if current_export['data_type'] == 'returns':
                    process_returns_with_manual_filter_global(export_id, access_token)
                elif current_export['data_type'] == 'orders':
                    process_orders_chunked_global(export_id, access_token)
                elif current_export['data_type'] == 'products':
                    process_products_chunked_global(export_id, access_token)
            except Exception as e:
                app.logger.error(f"Background process error: {e}")
                # Update global store with error
                export_id = export_data.get('export_id')
                if export_id and export_id in export_progress_store:
                    export_progress_store[export_id]['error'] = str(e)
                    export_progress_store[export_id]['status'] = 'error'
        
        # Start thread and return immediately
        thread = threading.Thread(target=background_process)
        thread.daemon = True
        thread.start()
        
        # Return immediately to prevent timeout
        return {"status": "started", "progress": 1.0, "message": "Export process started"}
            
    except Exception as e:
        print(f"EXCEPTION in start_chunked_export: {e}")
        app.logger.error(f"EXCEPTION in start_chunked_export: {e}")
        export_data['error'] = str(e)
        export_data['status'] = 'error'
        session.modified = True
        return {"error": str(e)}

def get_date_chunks(start_date_str, end_date_str, chunk_days=3):
    """Pecah date range jadi chunks maksimal 3 hari (dikurangi dari 7 hari)"""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    chunks = []
    current = start_date
    while current < end_date:
        chunk_end = min(current + timedelta(days=chunk_days), end_date)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)  # Next chunk starts next day
    
    return chunks

def save_checkpoint(export_id, checkpoint_data):
    """Simpan checkpoint ke global store"""
    if export_id in export_progress_store:
        export_progress_store[export_id]['checkpoint'] = checkpoint_data
        app.logger.info(f"Checkpoint saved for export {export_id}: {checkpoint_data}")

def load_checkpoint(export_id):
    """Load checkpoint dari global store"""
    if export_id in export_progress_store:
        return export_progress_store[export_id].get('checkpoint', {})
    return {}

def get_order_details(order_sn, shop_id, access_token):
    """Get complete order details including payment method, create time, and shipping info"""
    try:
        # Call orders API menggunakan GET method yang benar
        order_params = {
            "order_sn_list": order_sn  # String format works
        }
        
        response, error = call_shopee_api("/api/v2/order/get_order_detail", method='GET', 
                                        shop_id=shop_id, access_token=access_token, body=order_params, max_retries=2)
        
        if error:
            app.logger.warning(f"Failed to get order details for {order_sn}: {error}")
            return {"payment_method": "API Error", "create_time": None, "shipping_info": {}}
            
        order_list = response.get('response', {}).get('order_list', [])
        if order_list and len(order_list) > 0:
            order_detail = order_list[0]
            
            # Check COD field (Cash on Delivery)
            is_cod = order_detail.get('cod', False)
            payment_method = "COD (Cash on Delivery)" if is_cod else "Online Payment"
            
            # Get order create time (tanggal order)
            order_create_time = order_detail.get('create_time')
            
            # Get REAL tracking number from logistics API
            real_tracking_number = ""
            try:
                tracking_params = {"order_sn": order_sn}
                tracking_response, tracking_error = call_shopee_api("/api/v2/logistics/get_tracking_number", method='GET', 
                                                                  shop_id=shop_id, access_token=access_token, body=tracking_params, max_retries=1)
                
                if tracking_response and not tracking_error:
                    real_tracking_number = tracking_response.get('response', {}).get('tracking_number', '')
                    app.logger.info(f"Found real tracking number for {order_sn}: {real_tracking_number}")
                else:
                    app.logger.warning(f"Could not get tracking number for {order_sn}: {tracking_error}")
                    
            except Exception as tracking_ex:
                app.logger.warning(f"Tracking API error for {order_sn}: {tracking_ex}")
            
            # Get shipping info with REAL tracking number
            shipping_info = {
                "tracking_number": real_tracking_number,  # REAL SPX tracking number (SPXID format)
                "package_number": order_detail.get('booking_sn', ''),  # Internal package number (fallback)
                "shipping_carrier": order_detail.get('shipping_carrier', ''),
                "order_status": order_detail.get('order_status', ''),
                "ship_by_date": order_detail.get('ship_by_date', ''),
                "advance_package": order_detail.get('advance_package', False),
            }
            
            # Debug: print all keys to see available fields
            app.logger.info(f"Order detail fields available: {list(order_detail.keys())}")
            app.logger.info(f"Order details for {order_sn}: payment={payment_method}, shipping_info={shipping_info}")
            
            return {
                "payment_method": payment_method,
                "create_time": order_create_time,
                "shipping_info": shipping_info
            }
        else:
            app.logger.warning(f"No order found for order_sn: {order_sn}")
            return {"payment_method": "Order tidak ditemukan", "create_time": None, "shipping_info": {}}
            
    except Exception as e:
        app.logger.error(f"Exception getting order details for {order_sn}: {e}")
        return {"payment_method": f"Error: {str(e)}", "create_time": None, "shipping_info": {}}

def process_chunk_data(chunk_returns, data_type='returns', shop_id=None, access_token=None):
    """Process data chunk dan return format Excel, lalu clear memory"""
    if not chunk_returns:
        return []
    
    processed_items = []
    
    for item in chunk_returns:
        if data_type == 'returns':
            # Lookup order details dari orders API
            order_sn = item.get('order_sn')
            order_details = {"payment_method": "Tidak tersedia", "create_time": None, "shipping_info": {}}
            
            if order_sn and shop_id and access_token:
                order_details = get_order_details(order_sn, shop_id, access_token)
                # Debug logging
                app.logger.info(f"DEBUG: order_sn={order_sn}, order_details={order_details}")
                print(f"DEBUG: order_sn={order_sn}, payment={order_details['payment_method']}")
                # Add delay to respect rate limiting (100 calls per minute = 0.6s per call)
                time.sleep(0.6)
            
            # Format dates
            return_create_time = datetime.fromtimestamp(item.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if item.get('create_time') else None
            order_create_time = datetime.fromtimestamp(order_details['create_time']).strftime('%Y-%m-%d %H:%M:%S') if order_details['create_time'] else None
            return_update_time = datetime.fromtimestamp(item.get('update_time')).strftime('%Y-%m-%d %H:%M:%S') if item.get('update_time') else None
            
            # Extract SKU codes, item names, dan quantities dari item array
            sku_codes = []
            item_names = []
            quantities = []
            items_data = item.get('item', [])
            for product_item in items_data:
                # Get both item_sku and variation_sku
                item_sku = product_item.get('item_sku', '')
                variation_sku = product_item.get('variation_sku', '')
                item_name = product_item.get('name', '')
                quantity = product_item.get('amount', 0)  # Get quantity
                
                # Use variation_sku if available, otherwise item_sku
                if variation_sku:
                    sku_codes.append(variation_sku)
                elif item_sku:
                    sku_codes.append(item_sku)
                
                if item_name:
                    item_names.append(item_name)
                
                if quantity:
                    quantities.append(str(quantity))
            
            # Join multiple SKUs, names, and quantities if there are multiple items
            sku_code_str = ' | '.join(filter(None, sku_codes)) if sku_codes else ''
            item_name_str = ' | '.join(item_names) if item_names else ''
            quantity_str = ' | '.join(quantities) if quantities else '0'
            
            processed_item = {
                "Nomor Pesanan": item.get('order_sn'),
                "Nomor Retur": item.get('return_sn'),
                "No Resi Retur": item.get('tracking_number', ''),  # Return tracking from returns API
                "No Resi Pengiriman": order_details['shipping_info'].get('tracking_number', ''),  # booking_sn is the tracking number
                "Tanggal Order": order_create_time,  # From order API
                "Tanggal Retur Diajukan": return_create_time,  # Return create time
                "Payment Method": order_details['payment_method'],  # COD vs Online Payment
                "SKU Code": sku_code_str,  # NEW: Extracted from item array
                "Nama Produk": item_name_str,  # BONUS: Product names
                "Qty": quantity_str,  # NEW: Product quantities
                "Status": item.get('status'),
                "Alasan": item.get('reason'),
                "Mata Uang": item.get('currency'),
                "Total Pengembalian Dana": item.get('refund_amount'),
                "Alasan Teks dari Pembeli": item.get('text_reason'),
                "Username Pembeli": item.get('user', {}).get('username') if item.get('user') else None,
                "Email Pembeli": item.get('user', {}).get('email') if item.get('user') else None,
                "Tanggal Update": return_update_time,
                "Tanggal Jatuh Tempo": datetime.fromtimestamp(item.get('due_date')).strftime('%Y-%m-%d %H:%M:%S') if item.get('due_date') else None,
                "Negotiation Status": item.get('negotiation_status'),
                "Needs Logistics": "Ya" if item.get('needs_logistics') else "Tidak"
            }
        else:
            # Default processing for other data types
            processed_item = item
        
        processed_items.append(processed_item)
    
    # Clear input data from memory
    del chunk_returns
    
    return processed_items

def process_returns_with_manual_filter_global(export_id, access_token):
    """Get ALL returns then filter manually by date - includes RRBOC returns like 2501010C4UCUTPB."""
    app.logger.info("=== STARTING process_returns_with_manual_filter_global ===")
    
    if export_id not in export_progress_store:
        return
    
    export_data = export_progress_store[export_id]
    export_data['status'] = 'processing'
    export_data['current_step'] = 'Mengambil SEMUA data lalu filter manual berdasarkan tanggal...'
    export_data['progress'] = 5.0
    
    # Parse user date filter
    try:
        from datetime import datetime
        date_from = datetime.strptime(export_data['date_from'], '%Y-%m-%d') if export_data['date_from'] else None
        date_to = datetime.strptime(export_data['date_to'], '%Y-%m-%d') if export_data['date_to'] else None
        
        # Add time bounds
        if date_from:
            date_from = date_from.replace(hour=0, minute=0, second=0)
        if date_to:
            date_to = date_to.replace(hour=23, minute=59, second=59)
            
        app.logger.info(f"Manual filter range: {date_from} to {date_to}")
    except:
        date_from = None 
        date_to = None
        app.logger.warning("Invalid date format, will export all data")
    
    # Load checkpoint if exists
    checkpoint = load_checkpoint(export_id)
    start_page_no = checkpoint.get('page_no', 1)
    
    shop_id = export_data['shop_id']
    all_raw_data = []  # Store raw return data
    total_processed = 0
    
    # Step 1: Get ALL returns without API date filter
    page_no = start_page_no
    max_pages_estimate = 100
    
    while True:
        app.logger.info(f"=== FETCHING PAGE {page_no} ===")
            
        # Update progress for fetching
        page_progress = min(page_no / max_pages_estimate, 0.9) * 50.0  # 50% for fetching
        current_progress = 5.0 + page_progress
        export_data['progress'] = round(min(55.0, current_progress), 1)
        export_data['current_step'] = f'Mengambil halaman {page_no} (semua data)...'
            
        # API call WITHOUT date filter - get ALL returns including RRBOC
        return_body = {"page_no": page_no, "page_size": 10}
            
        response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                        shop_id=shop_id, access_token=access_token, body=return_body)
            
        if error:
            export_data['error'] = f"Gagal mengambil daftar retur: {error}"
            export_data['status'] = 'error'
            return
                
        return_list = response.get('response', {}).get('return', [])
        if not return_list:
            break
                
        # Store raw data for manual filtering
        all_raw_data.extend(return_list)
        total_processed += len(return_list)
        
        time.sleep(0.6)
        page_no += 1
            
        if page_no > 200:
            break
    
    app.logger.info(f"Fetched {len(all_raw_data)} total returns from API")
    
    # Step 2: Manual date filtering
    export_data['current_step'] = 'Filtering data berdasarkan tanggal...'
    export_data['progress'] = 60.0
    
    filtered_returns = []
    if date_from and date_to:
        for return_item in all_raw_data:
            create_time = return_item.get('create_time')
            if create_time:
                try:
                    return_date = datetime.fromtimestamp(create_time)
                    if date_from <= return_date <= date_to:
                        filtered_returns.append(return_item)
                except:
                    continue
    else:
        # No date filter, use all data
        filtered_returns = all_raw_data
    
    app.logger.info(f"After date filtering: {len(filtered_returns)} returns match criteria")
    print(f"Manual filter result: {len(filtered_returns)}/{len(all_raw_data)} returns match date range")
    
    # Step 3: Process filtered data
    export_data['current_step'] = 'Memproses data yang sudah difilter...'
    export_data['progress'] = 75.0
    
    if filtered_returns:
        processed_data = process_chunk_data(filtered_returns, 'returns', shop_id, access_token)
        
        # Log if specific return found
        target_return = "2501010C4UCUTPB"
        found_target = any(item.get('Nomor Retur') == target_return for item in processed_data)
        if found_target:
            app.logger.info(f"SUCCESS: Found target return {target_return} in filtered results!")
            print(f"✅ Found {target_return} in export results!")
        
        export_data['data'] = processed_data
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = f'Selesai! {len(processed_data)} retur berhasil diproses (MANUAL FILTER + RRBOC)'
        
        app.logger.info(f"Export completed with {len(processed_data)} records (MANUAL DATE FILTER)")
    else:
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = 'Tidak ada data retur dalam rentang tanggal yang dipilih'
        export_data['data'] = []
    
    # Clean up
    del all_raw_data
    if 'filtered_returns' in locals():
        del filtered_returns
    
    # Clear checkpoint after completion
    if export_id in export_progress_store:
        export_progress_store[export_id].pop('checkpoint', None)

def process_returns_with_date_filter_global(export_id, access_token):
    """Process returns data WITH date filter (original logic) - excludes RRBOC returns."""
    app.logger.info("=== STARTING process_returns_with_date_filter_global (WITH DATE FILTER) ===")
    
    if export_id not in export_progress_store:
        return
    
    export_data = export_progress_store[export_id]
    export_data['status'] = 'processing'
    export_data['current_step'] = 'Mempersiapkan chunks tanggal...'
    export_data['progress'] = 5.0
    
    # Load checkpoint if exists
    checkpoint = load_checkpoint(export_id)
    start_chunk_index = checkpoint.get('chunk_index', 0)
    start_page_no = checkpoint.get('page_no', 1)
    
    app.logger.info(f"Shop ID: {export_data['shop_id']}")
    app.logger.info(f"WITH DATE FILTER - excludes RRBOC returns")
    app.logger.info(f"Date range: {export_data['date_from']} to {export_data['date_to']}")
    
    # Use date chunks with filter (original logic)
    date_chunks = get_date_chunks(export_data['date_from'], export_data['date_to'], 3)
    app.logger.info(f"Created {len(date_chunks)} date chunks")
    
    shop_id = export_data['shop_id']
    all_processed_data = []
    total_processed = 0
    
    # Loop through date chunks with filter
    for chunk_index, (chunk_start, chunk_end) in enumerate(date_chunks):
        if chunk_index < start_chunk_index:
            continue
            
        app.logger.info(f"Processing chunk {chunk_index + 1}/{len(date_chunks)}: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        
        chunk_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0
        export_data['progress'] = round(chunk_progress, 1)
        export_data['current_step'] = f'Memproses chunk {chunk_index + 1}/{len(date_chunks)} ({chunk_start.strftime("%Y-%m-%d")} to {chunk_end.strftime("%Y-%m-%d")})'
        
        page_no = start_page_no if chunk_index == start_chunk_index else 1
        chunk_returns = []
        
        while True:
            page_progress = min(page_no / 50, 0.9) * (75.0 / len(date_chunks))
            current_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0 + page_progress
            export_data['progress'] = round(min(85.0, current_progress), 1)
            export_data['current_step'] = f'Chunk {chunk_index + 1}/{len(date_chunks)} - Halaman {page_no}...'
            
            # API call WITH date filter (original logic)
            return_body = {
                "page_no": page_no, 
                "page_size": 10,
                "create_time_from": int(chunk_start.timestamp()),
                "create_time_to": int(chunk_end.timestamp())
            }
            
            response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                            shop_id=shop_id, access_token=access_token, body=return_body)
            
            if error:
                export_data['error'] = f"Gagal mengambil daftar retur: {error}"
                export_data['status'] = 'error'
                return
                
            return_list = response.get('response', {}).get('return', [])
            if not return_list:
                break
                
            chunk_returns.extend(return_list)
            total_processed += len(return_list)
            
            time.sleep(0.6)
            page_no += 1
            
            if page_no > 40:
                break
        
        # Process chunk data
        if chunk_returns:
            processed_chunk_data = process_chunk_data(chunk_returns, 'returns', shop_id, access_token)
            all_processed_data.extend(processed_chunk_data)
            del chunk_returns
            del processed_chunk_data
        
        start_page_no = 1
    
    # Finalize export
    export_data['current_step'] = 'Menyelesaikan export...'
    export_data['progress'] = 95.0
    
    if all_processed_data:
        export_data['data'] = all_processed_data
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = f'Selesai! {len(all_processed_data)} retur berhasil diproses (DENGAN FILTER TANGGAL)'
        
        app.logger.info(f"Export completed with {len(all_processed_data)} records (WITH DATE FILTER)")
        
        if export_id in export_progress_store:
            export_progress_store[export_id].pop('checkpoint', None)
    else:
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = 'Tidak ada data retur ditemukan dalam rentang tanggal'
        export_data['data'] = []
    
    del all_processed_data

def process_orders_chunked_global(export_id, access_token):
    """Process orders data in small chunks using global store."""
    app.logger.info("=== STARTING process_orders_chunked_global ===")
    
    if export_id not in export_progress_store:
        return
    
    export_data = export_progress_store[export_id]
    export_data['status'] = 'processing'
    export_data['current_step'] = 'Mempersiapkan chunks tanggal untuk orders...'
    export_data['progress'] = 5.0
    
    app.logger.info(f"Initial progress set to: {export_data['progress']}")
    app.logger.info(f"Shop ID: {export_data['shop_id']}")
    app.logger.info(f"Date range: {export_data['date_from']} to {export_data['date_to']}")
    
    # Pecah date range jadi chunks 15 hari
    date_chunks = get_date_chunks(export_data['date_from'], export_data['date_to'], 15)
    app.logger.info(f"Created {len(date_chunks)} date chunks for orders")
    
    shop_id = export_data['shop_id']
    all_orders = []
    total_processed = 0
    
    # Loop untuk setiap chunk tanggal
    for chunk_index, (chunk_start, chunk_end) in enumerate(date_chunks):
        app.logger.info(f"Processing orders chunk {chunk_index + 1}/{len(date_chunks)}: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        
        # Update progress untuk chunk
        chunk_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0
        export_data['progress'] = round(chunk_progress, 1)
        export_data['current_step'] = f'Memproses orders chunk {chunk_index + 1}/{len(date_chunks)} ({chunk_start.strftime("%Y-%m-%d")} to {chunk_end.strftime("%Y-%m-%d")})'
        
        # Reset pagination untuk chunk ini
        page_no = 1
        max_pages_estimate = 50
        
        # Loop pagination untuk chunk ini
        while True:
            app.logger.info(f"=== ORDERS CHUNK {chunk_index + 1} PAGE {page_no} ===")
            
            # Update progress dalam chunk (fixed calculation)
            chunk_base_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0
            chunk_size_progress = 75.0 / len(date_chunks)
            page_progress = min(page_no / max_pages_estimate, 0.9) * chunk_size_progress
            current_progress = chunk_base_progress + page_progress
            export_data['progress'] = round(min(85.0, current_progress), 1)
            export_data['current_step'] = f'Orders Chunk {chunk_index + 1}/{len(date_chunks)} - Halaman {page_no}...'
            
            # API call untuk orders dengan date filter
            order_body = {
                "page_no": page_no,
                "page_size": 20,  # Larger page size for orders
                "time_range_field": "create_time",
                "time_from": int(chunk_start.timestamp()),
                "time_to": int(chunk_end.timestamp())
                # Removed order_status parameter as "ALL" is not valid
            }
            
            response, error = call_shopee_api("/api/v2/order/get_order_list", method='GET', 
                                            shop_id=shop_id, access_token=access_token, body=order_body)
            
            if error:
                app.logger.error(f"Orders API error: {error}")
                export_data['error'] = f"Gagal mengambil daftar pesanan: {error}"
                export_data['status'] = 'error'
                return
            
            # Process response
            order_list = response.get('response', {}).get('order_list', [])
            app.logger.info(f"Found {len(order_list)} orders on chunk {chunk_index + 1} page {page_no}")
            
            if not order_list:
                app.logger.info(f"No more orders found in chunk {chunk_index + 1}, breaking pagination loop")
                break
            
            all_orders.extend(order_list)
            total_processed += len(order_list)
            
            # Add delay to prevent rate limiting (100 calls per minute = 0.6s per call)
            time.sleep(0.6)
            page_no += 1
            
            # Safety limit per chunk
            if page_no > 100:
                app.logger.info(f"Reached safety limit of 100 pages in orders chunk {chunk_index + 1}")
                break
        
        app.logger.info(f"Orders chunk {chunk_index + 1} completed")
    
    # Process the collected data
    export_data['current_step'] = 'Memproses data orders untuk Excel...'
    export_data['progress'] = 95.0
    
    if all_orders:
        processed_orders = []
        app.logger.info(f"Processing {len(all_orders)} total orders")
        
        for order in all_orders:
            processed_item = {
                "Nomor Pesanan": order.get('order_sn'),
                "Status Pesanan": order.get('order_status'),
                "Tanggal Dibuat": datetime.fromtimestamp(order.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if order.get('create_time') else None,
                "Tanggal Update": datetime.fromtimestamp(order.get('update_time')).strftime('%Y-%m-%d %H:%M:%S') if order.get('update_time') else None,
                "Total Harga": order.get('total_amount'),
                "Mata Uang": order.get('currency'),
                "Metode Pembayaran": order.get('payment_method'),
                "Estimasi Pengiriman": order.get('estimated_shipping_fee'),
                "Resi": order.get('tracking_number'),
                "Pesan dari Pembeli": order.get('message_to_seller'),
                "Negara": order.get('recipient_address', {}).get('country') if order.get('recipient_address') else None,
                "Kota": order.get('recipient_address', {}).get('city') if order.get('recipient_address') else None
            }
            processed_orders.append(processed_item)
        
        export_data['data'] = processed_orders
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = f'Selesai! {len(processed_orders)} pesanan berhasil diproses'
        
        app.logger.info(f"Orders export completed with {len(processed_orders)} records")
    else:
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = 'Tidak ada data pesanan ditemukan'
        export_data['data'] = []

def process_products_chunked_global(export_id, access_token):
    """Process products data in small chunks using global store."""
    if export_id not in export_progress_store:
        return
    export_data = export_progress_store[export_id]
    export_data['status'] = 'completed'  # Placeholder
    export_data['progress'] = 100
    export_data['current_step'] = 'Products processing not implemented yet'
    export_data['data'] = []

@app.route('/download_export')
def download_export():
    """Download the completed export as Excel file."""
    export_data = session.get('current_export')
    if not export_data:
        flash("Tidak ada data ekspor yang siap untuk diunduh.", 'warning')
        return redirect(url_for('dashboard'))
    
    # Get the latest data from global store
    export_id = export_data.get('export_id')
    if export_id and export_id in export_progress_store:
        export_data = export_progress_store[export_id]
        # Update session with latest data (WITHOUT the data field to reduce cookie size)
        session_data = export_data.copy()
        session_data.pop('data', None)  # Remove data from session to fix cookie size
        session['current_export'] = session_data
        session.modified = True
    
    if export_data['status'] != 'completed':
        flash("Ekspor belum selesai. Status: " + export_data.get('status', 'unknown'), 'warning')
        return redirect(url_for('dashboard'))
    
    if not export_data.get('data'):
        flash("Tidak ada data untuk diekspor.", 'warning')
        return redirect(url_for('dashboard'))
    
    df = pd.DataFrame(export_data['data'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=export_data['data_type'])
    output.seek(0)
    
    filename = f"laporan_{export_data['data_type']}_{export_data['shop_id']}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    response = make_response(output.read())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Clear the export data from session
    session.pop('current_export', None)
    session.modified = True
    
    # Auto-cleanup: Remove data from memory store after successful download
    export_id = export_data.get('export_id')
    if export_id and export_id in export_progress_store:
        del export_progress_store[export_id]
        print(f"Auto-cleanup: Removed export data {export_id} from memory after download")
        app.logger.info(f"Auto-cleanup: Removed export data {export_id} from memory after download")
    
    return response

# ==============================================================================
# ENTRY POINT UNTUK MENJALANKAN APLIKASI
# ==============================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
