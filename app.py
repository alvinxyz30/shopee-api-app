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

def call_shopee_api(path, method='POST', shop_id=None, access_token=None, body=None):
    """Fungsi generik untuk memanggil semua endpoint Shopee API v2."""
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

    try:
        if method.upper() == 'POST':
            response = requests.post(full_url, params=params, json=body, headers=headers, timeout=30)
        else:
            response = requests.get(full_url, params={**params, **(body or {})}, headers=headers, timeout=30)
        
        response.raise_for_status()
        response_data = response.json()
        
        if response_data.get("error"):
            error_msg = f"Shopee API Error: {response_data.get('message', 'Unknown error')} (Req ID: {response_data.get('request_id')})"
            app.logger.error(error_msg)
            return None, error_msg
            
        return response_data, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Kesalahan Jaringan: {e}"
        app.logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"Terjadi kesalahan tak terduga: {e}"
        app.logger.error(error_msg)
        return None, error_msg

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

def get_date_chunks(start_date_str, end_date_str, chunk_days=15):
    """Pecah date range jadi chunks maksimal 15 hari"""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    chunks = []
    current = start_date
    while current < end_date:
        chunk_end = min(current + timedelta(days=chunk_days), end_date)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)  # Next chunk starts next day
    
    return chunks

def process_returns_chunked_global(export_id, access_token):
    """Process returns data in small chunks using global store."""
    app.logger.info("=== STARTING process_returns_chunked_global ===")
    
    if export_id not in export_progress_store:
        return
    
    export_data = export_progress_store[export_id]
    export_data['status'] = 'processing'
    export_data['current_step'] = 'Mempersiapkan chunks tanggal...'
    export_data['progress'] = 5.0  # Start with 5%
    
    app.logger.info(f"Initial progress set to: {export_data['progress']}")
    app.logger.info(f"Shop ID: {export_data['shop_id']}")
    app.logger.info(f"Access token length: {len(access_token) if access_token else 'None'}")
    app.logger.info(f"Date range: {export_data['date_from']} to {export_data['date_to']}")
    
    # Pecah date range jadi chunks 15 hari
    date_chunks = get_date_chunks(export_data['date_from'], export_data['date_to'], 15)
    print(f"=== DATE CHUNKING ===")
    print(f"Total chunks: {len(date_chunks)}")
    for i, (start, end) in enumerate(date_chunks):
        print(f"Chunk {i+1}: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    app.logger.info(f"Created {len(date_chunks)} date chunks")
    
    shop_id = export_data['shop_id']
    all_returns = []
    total_processed = 0
    
    # Loop untuk setiap chunk tanggal
    for chunk_index, (chunk_start, chunk_end) in enumerate(date_chunks):
        print(f"=== PROCESSING CHUNK {chunk_index + 1}/{len(date_chunks)} ===")
        print(f"Date range: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        app.logger.info(f"Processing chunk {chunk_index + 1}/{len(date_chunks)}: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
        
        # Update progress untuk chunk
        chunk_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0  # 75% untuk semua chunks
        export_data['progress'] = round(chunk_progress, 1)
        export_data['current_step'] = f'Memproses chunk {chunk_index + 1}/{len(date_chunks)} ({chunk_start.strftime("%Y-%m-%d")} to {chunk_end.strftime("%Y-%m-%d")})'
        
        # Reset pagination untuk chunk ini
        page_no = 1
        max_pages_estimate = 50
        
        # Loop pagination untuk chunk ini
        while True:
            app.logger.info(f"=== CHUNK {chunk_index + 1} PAGE {page_no} ===")
            
            # Update progress dalam chunk
            page_progress = (page_no / max_pages_estimate) * (75.0 / len(date_chunks))  # Progress dalam chunk
            current_progress = 5.0 + (chunk_index / len(date_chunks)) * 75.0 + page_progress
            export_data['progress'] = round(min(85.0, current_progress), 1)
            export_data['current_step'] = f'Chunk {chunk_index + 1}/{len(date_chunks)} - Halaman {page_no}...'
            
            app.logger.info(f"Progress updated to: {export_data['progress']}")
            app.logger.info(f"Calling API for chunk {chunk_index + 1} page {page_no}...")
            
            # API call dengan date filter
            return_body = {
                "page_no": page_no, 
                "page_size": 5,  # Small batch size
                "create_time_from": int(chunk_start.timestamp()),
                "create_time_to": int(chunk_end.timestamp())
            }
            
            print(f"API call with date filter: {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
            response, error = call_shopee_api("/api/v2/returns/get_return_list", method='GET', 
                                            shop_id=shop_id, access_token=access_token, body=return_body)
            
            app.logger.info(f"API response received. Error: {error}")
            
            if error:
                app.logger.error(f"Returns API error: {error}")
                export_data['error'] = f"Gagal mengambil daftar retur: {error}"
                export_data['status'] = 'error'
                return
                
            # Debug logging
            return_list = response.get('response', {}).get('return', [])
            app.logger.info(f"Found {len(return_list)} returns on chunk {chunk_index + 1} page {page_no}")
            
            # Log sample data for debugging
            if return_list:
                sample_return = return_list[0]
                print(f"=== CHUNK {chunk_index + 1} PAGE {page_no} SAMPLE DATA ===")
                print(f"Return SN: {sample_return.get('return_sn')}")
                print(f"Order SN: {sample_return.get('order_sn')}")
                print(f"Status: {sample_return.get('status')}")
                print(f"Create Time: {datetime.fromtimestamp(sample_return.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if sample_return.get('create_time') else 'None'}")
                print(f"Refund Amount: {sample_return.get('refund_amount')}")
                print(f"====================")
                
            # Log all return_sn for tracking
            return_sns = [ret.get('return_sn') for ret in return_list]
            app.logger.info(f"Chunk {chunk_index + 1} page {page_no} return_sn list: {return_sns}")
            print(f"Chunk {chunk_index + 1} page {page_no} return_sn: {return_sns}")
            
            if not return_list:
                app.logger.info(f"No more returns found in chunk {chunk_index + 1}, breaking pagination loop")
                print(f"No more data in chunk {chunk_index + 1}, moving to next chunk")
                break
                
            all_returns.extend(return_list)
            total_processed += len(return_list)
            
            app.logger.info(f"Chunk {chunk_index + 1} progress: {current_progress:.1f}%, total processed: {total_processed}")
            print(f"Total processed so far: {total_processed}")
            
            # Add delay to prevent rate limiting
            time.sleep(2)  # Increased delay
            page_no += 1
            
            # Safety limit per chunk
            if page_no > 200:  # Max 1000 records per chunk (200 * 5)
                app.logger.info(f"Reached safety limit of 200 pages in chunk {chunk_index + 1}")
                print(f"Safety limit reached in chunk {chunk_index + 1}")
                break
        
        print(f"=== CHUNK {chunk_index + 1} COMPLETED ===")
        print(f"Total returns from chunk {chunk_index + 1}: {len([r for r in all_returns[-total_processed:]])}")
        app.logger.info(f"Chunk {chunk_index + 1} completed")
    
    # Process the collected data
    export_data['current_step'] = 'Memproses data untuk Excel...'
    export_data['progress'] = 95.0
    
    if all_returns:
        processed_returns = []
        print(f"=== PROCESSING {len(all_returns)} RETURNS ===")
        app.logger.info(f"Processing {len(all_returns)} total returns")
        
        for i, ret in enumerate(all_returns):
            processed_item = {
                "Nomor Pesanan": ret.get('order_sn'),
                "Nomor Retur": ret.get('return_sn'),
                "Status": ret.get('status'),
                "Alasan": ret.get('reason'),
                "Tanggal Dibuat": datetime.fromtimestamp(ret.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if ret.get('create_time') else None,
                "Metode Pembayaran": ret.get('payment_method'),
                "Resi Pengembalian": ret.get('logistics', {}).get('tracking_number') if ret.get('logistics') else None,
                "Total Pengembalian Dana": ret.get('refund_amount'),
                "Alasan Teks dari Pembeli": ret.get('text_reason'),
                "User ID": ret.get('user_id'),
                "Tanggal Update": datetime.fromtimestamp(ret.get('update_time')).strftime('%Y-%m-%d %H:%M:%S') if ret.get('update_time') else None
            }
            processed_returns.append(processed_item)
            
            # Log every 10th item or first/last items
            if i % 10 == 0 or i == 0 or i == len(all_returns) - 1:
                print(f"Processed item {i+1}: {processed_item['Nomor Retur']}")
                app.logger.info(f"Processed item {i+1}: {processed_item}")
        
        export_data['data'] = processed_returns
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = f'Selesai! {len(processed_returns)} retur berhasil diproses'
        
        print(f"=== EXPORT COMPLETED ===")
        print(f"Total records processed: {len(processed_returns)}")
        app.logger.info(f"Export completed with {len(processed_returns)} records")
    else:
        export_data['status'] = 'completed'
        export_data['progress'] = 100.0
        export_data['current_step'] = 'Tidak ada data retur ditemukan'
        export_data['data'] = []

def process_orders_chunked_global(export_id, access_token):
    """Process orders data in small chunks using global store."""
    if export_id not in export_progress_store:
        return
    export_data = export_progress_store[export_id]
    export_data['status'] = 'completed'  # Placeholder
    export_data['progress'] = 100
    export_data['current_step'] = 'Orders processing not implemented yet'
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
    if not export_data or export_data['status'] != 'completed':
        flash("Tidak ada data ekspor yang siap untuk diunduh.", 'warning')
        return redirect(url_for('dashboard'))
    
    if not export_data['data']:
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
    
    return response

# ==============================================================================
# ENTRY POINT UNTUK MENJALANKAN APLIKASI
# ==============================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
