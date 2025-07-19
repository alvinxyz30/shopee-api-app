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

    # DIKEMBALIKAN: Menggunakan endpoint /api/v2/shop/get_shop_info yang lebih standar
    path_info = "/api/v2/shop/get_shop_info"
    info_data, error = call_shopee_api(path_info, method='GET', shop_id=int(shop_id_str), access_token=access_token)
    shop_name = f"Toko {shop_id_str}"
    if error:
        flash(f"Gagal mendapatkan info nama toko: {error}. Menggunakan ID sebagai nama.", 'warning')
    else:
        shop_name = info_data.get('response', {}).get('shop_name', shop_name)

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

@app.route('/test_returns_api')
def test_returns_api():
    """Test returns API to debug issues."""
    shops = session.get('shops', {})
    if not shops:
        return {"error": "No shops found in session"}, 400
    
    # Get first shop for testing
    shop_id, shop_data = next(iter(shops.items()))
    access_token = shop_data['access_token']
    
    # Test single API call
    return_body = {"page_no": 1, "page_size": 5}
    response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                    shop_id=shop_id, access_token=access_token, body=return_body)
    
    return {
        "shop_id": shop_id,
        "api_response": response,
        "error": error,
        "url_called": f"{BASE_URL}/api/v2/returns/get_return_list"
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
    
    # Test multiple API variations
    results = {}
    
    # Try 1: GET with order_sn_list as string
    order_params1 = {"order_sn_list": order_sn}
    response1, error1 = call_shopee_api("/api/v2/order/get_order_detail", method='GET', 
                                      shop_id=shop_id, access_token=access_token, body=order_params1)
    results["test1_get_string"] = {"response": response1, "error": error1}
    
    # Try 2: GET with order_sn_list as array
    order_params2 = {"order_sn_list": [order_sn]}
    response2, error2 = call_shopee_api("/api/v2/order/get_order_detail", method='GET', 
                                      shop_id=shop_id, access_token=access_token, body=order_params2)
    results["test2_get_array"] = {"response": response2, "error": error2}
    
    # Try 3: POST with body
    order_body = {"order_sn_list": [order_sn]}
    response3, error3 = call_shopee_api("/api/v2/order/get_order_detail", method='POST', 
                                      shop_id=shop_id, access_token=access_token, body=order_body)
    results["test3_post"] = {"response": response3, "error": error3}
    
    # Try 4: Alternative endpoint - get_order_list with specific order
    order_list_params = {"order_sn_list": [order_sn]}
    response4, error4 = call_shopee_api("/api/v2/order/get_order_list", method='GET', 
                                      shop_id=shop_id, access_token=access_token, body=order_list_params)
    results["test4_order_list"] = {"response": response4, "error": error4}
    
    return {
        "shop_id": shop_id,
        "order_sn": order_sn,
        "api_tests": results
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
    
    shop_data = session.get('shops', {}).get(shop_id)
    if not shop_data:
        flash(f"Toko dengan ID {shop_id} tidak ditemukan di sesi ini.", 'danger')
        return redirect(url_for('dashboard'))
    
    # Initialize progress tracking in global store and session
    export_id = f"{shop_id}_{data_type}_{int(time.time())}"
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
                    process_returns_chunked_global(export_id, access_token)
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

def get_payment_method_from_order(order_sn, shop_id, access_token):
    """Lookup payment method dari orders API menggunakan order_sn"""
    try:
        # Call orders API menggunakan GET method yang benar
        order_params = {
            "order_sn_list": order_sn  # String format works
        }
        
        response, error = call_shopee_api("/api/v2/order/get_order_detail", method='GET', 
                                        shop_id=shop_id, access_token=access_token, body=order_params, max_retries=2)
        
        if error:
            app.logger.warning(f"Failed to get payment method for order {order_sn}: {error}")
            return "API Error"
            
        order_list = response.get('response', {}).get('order_list', [])
        if order_list and len(order_list) > 0:
            order_detail = order_list[0]
            
            # Check COD field (Cash on Delivery)
            is_cod = order_detail.get('cod', False)
            if is_cod:
                payment_method = "COD (Cash on Delivery)"
            else:
                # If not COD, assume online payment
                payment_method = "Online Payment"
            
            app.logger.info(f"Payment method for order {order_sn}: {payment_method} (COD: {is_cod})")
            return payment_method
        else:
            app.logger.warning(f"No order found for order_sn: {order_sn}")
            return "Order tidak ditemukan"
            
    except Exception as e:
        app.logger.error(f"Exception getting payment method for order {order_sn}: {e}")
        return f"Error: {str(e)}"

def process_chunk_data(chunk_returns, data_type='returns', shop_id=None, access_token=None):
    """Process data chunk dan return format Excel, lalu clear memory"""
    if not chunk_returns:
        return []
    
    processed_items = []
    
    for item in chunk_returns:
        if data_type == 'returns':
            # Lookup payment method dari orders API
            order_sn = item.get('order_sn')
            payment_method = None
            if order_sn and shop_id and access_token:
                payment_method = get_payment_method_from_order(order_sn, shop_id, access_token)
                # Debug logging
                app.logger.info(f"DEBUG: order_sn={order_sn}, payment_method={payment_method}")
                print(f"DEBUG: order_sn={order_sn}, payment_method={payment_method}")
                # Add delay to respect rate limiting
                time.sleep(0.2)
            
            processed_item = {
                "Nomor Pesanan": item.get('order_sn'),
                "Nomor Retur": item.get('return_sn'),
                "Status": item.get('status'),
                "Alasan": item.get('reason'),
                "Tanggal Dibuat": datetime.fromtimestamp(item.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if item.get('create_time') else None,
                "Mata Uang": item.get('currency'),
                "Metode Pembayaran": payment_method,  # Added: From orders API lookup
                "Resi Pengembalian": item.get('tracking_number'),  # Fixed: Direct field access
                "Total Pengembalian Dana": item.get('refund_amount'),
                "Alasan Teks dari Pembeli": item.get('text_reason'),
                "Username Pembeli": item.get('user', {}).get('username') if item.get('user') else None,
                "Email Pembeli": item.get('user', {}).get('email') if item.get('user') else None,
                "Tanggal Update": datetime.fromtimestamp(item.get('update_time')).strftime('%Y-%m-%d %H:%M:%S') if item.get('update_time') else None,
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

def process_returns_chunked_global(export_id, access_token):
    """Process returns data with checkpoint system and memory management."""
    app.logger.info("=== STARTING process_returns_chunked_global ===")
    
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
    
    app.logger.info(f"Initial progress set to: {export_data['progress']}")
    app.logger.info(f"Shop ID: {export_data['shop_id']}")
    app.logger.info(f"Checkpoint: start_chunk={start_chunk_index}, start_page={start_page_no}")
    app.logger.info(f"Date range: {export_data['date_from']} to {export_data['date_to']}")
    
    # Pecah date range jadi chunks 3 hari (dikurangi dari 7 hari)
    date_chunks = get_date_chunks(export_data['date_from'], export_data['date_to'], 3)
    print(f"=== DATE CHUNKING ===")
    print(f"Total chunks: {len(date_chunks)}")
    for i, (start, end) in enumerate(date_chunks):
        print(f"Chunk {i+1}: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    app.logger.info(f"Created {len(date_chunks)} date chunks")
    
    shop_id = export_data['shop_id']
    all_processed_data = []  # Store processed data instead of raw data
    total_processed = 0
    
    # Loop untuk setiap chunk tanggal
    for chunk_index, (chunk_start, chunk_end) in enumerate(date_chunks):
        # Skip chunks that already processed (resume from checkpoint)
        if chunk_index < start_chunk_index:
            continue
            
        print(f"=== PROCESSING CHUNK {chunk_index + 1}/{len(date_chunks)} ===")
        print(f"Date range: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        app.logger.info(f"Processing chunk {chunk_index + 1}/{len(date_chunks)}: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        
        # Update progress untuk chunk
        chunk_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0
        export_data['progress'] = round(chunk_progress, 1)
        export_data['current_step'] = f'Memproses chunk {chunk_index + 1}/{len(date_chunks)} ({chunk_start.strftime("%Y-%m-%d")} to {chunk_end.strftime("%Y-%m-%d")})'
        
        # Reset pagination untuk chunk ini atau resume dari checkpoint
        page_no = start_page_no if chunk_index == start_chunk_index else 1
        max_pages_estimate = 50
        chunk_returns = []  # Store returns for current chunk only
        
        # Loop pagination untuk chunk ini
        while True:
            app.logger.info(f"=== CHUNK {chunk_index + 1} PAGE {page_no} ===")
            
            # Update progress dalam chunk (fixed calculation)
            chunk_base_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0
            chunk_size_progress = 75.0 / len(date_chunks)
            page_progress = min(page_no / max_pages_estimate, 0.9) * chunk_size_progress
            current_progress = chunk_base_progress + page_progress
            export_data['progress'] = round(min(85.0, current_progress), 1)
            export_data['current_step'] = f'Chunk {chunk_index + 1}/{len(date_chunks)} - Halaman {page_no}...'
            
            # Save checkpoint every 10 pages (more frequent)
            if page_no % 10 == 0:
                checkpoint_data = {
                    'chunk_index': chunk_index,
                    'page_no': page_no,
                    'total_processed': total_processed
                }
                save_checkpoint(export_id, checkpoint_data)
            
            app.logger.info(f"Progress updated to: {export_data['progress']}")
            app.logger.info(f"Calling API for chunk {chunk_index + 1} page {page_no}...")
            
            # API call dengan date filter
            return_body = {
                "page_no": page_no, 
                "page_size": 1,  # Minimal batch size for maximum stability
                "create_time_from": int(chunk_start.timestamp()),
                "create_time_to": int(chunk_end.timestamp())
            }
            
            print(f"API call with date filter: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
            response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                            shop_id=shop_id, access_token=access_token, body=return_body)
            
            app.logger.info(f"API response received. Error: {error}")
            
            if error:
                app.logger.error(f"Returns API error: {error}")
                # Save checkpoint before error
                save_checkpoint(export_id, {
                    'chunk_index': chunk_index,
                    'page_no': page_no,
                    'total_processed': total_processed,
                    'error': True
                })
                export_data['error'] = f"Gagal mengambil daftar retur: {error}"
                export_data['status'] = 'error'
                return
                
            # Debug logging
            return_list = response.get('response', {}).get('return', [])
            app.logger.info(f"Found {len(return_list)} returns on chunk {chunk_index + 1} page {page_no}")
            
            if not return_list:
                app.logger.info(f"No more returns found in chunk {chunk_index + 1}, breaking pagination loop")
                print(f"No more data in chunk {chunk_index + 1}, moving to next chunk")
                break
                
            chunk_returns.extend(return_list)
            total_processed += len(return_list)
            
            app.logger.info(f"Chunk {chunk_index + 1} progress: {current_progress:.1f}%, total processed: {total_processed}")
            print(f"Total processed so far: {total_processed}")
            
            # Add delay to respect rate limit (increased for stability)
            time.sleep(0.5)  # Increased delay for better stability
            page_no += 1
            
            # Safety limit per chunk (adjusted for page_size=1)
            if page_no > 400:  # Increased limit since page_size=1 (same total: 400*1=400 records)
                app.logger.info(f"Reached safety limit of 400 pages in chunk {chunk_index + 1}")
                print(f"Safety limit reached in chunk {chunk_index + 1}")
                break
        
        # Process chunk data and clear memory
        if chunk_returns:
            processed_chunk_data = process_chunk_data(chunk_returns, 'returns', shop_id, access_token)
            all_processed_data.extend(processed_chunk_data)
            app.logger.info(f"Processed {len(processed_chunk_data)} items from chunk {chunk_index + 1}")
            print(f"Processed {len(processed_chunk_data)} items from chunk {chunk_index + 1}")
            
            # Clear chunk data from memory
            del chunk_returns
            del processed_chunk_data
        
        print(f"=== CHUNK {chunk_index + 1} COMPLETED ===")
        app.logger.info(f"Chunk {chunk_index + 1} completed")
        
        # Reset start_page_no for next chunk
        start_page_no = 1
    
    # Finalize export
    export_data['current_step'] = 'Menyelesaikan export...'
    export_data['progress'] = 95.0
    
    if all_processed_data:
        export_data['data'] = all_processed_data
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = f'Selesai! {len(all_processed_data)} retur berhasil diproses'
        
        print(f"=== EXPORT COMPLETED ===")
        print(f"Total records processed: {len(all_processed_data)}")
        app.logger.info(f"Export completed with {len(all_processed_data)} records")
        
        # Clear checkpoint after successful completion
        if export_id in export_progress_store:
            export_progress_store[export_id].pop('checkpoint', None)
    else:
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = 'Tidak ada data retur ditemukan'
        export_data['data'] = []
    
    # Clear processed data from memory
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
            
            # Add delay to prevent rate limiting
            time.sleep(1)
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
