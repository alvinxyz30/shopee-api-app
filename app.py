# -*- coding: utf-8 -*-
import os
import time
import hmac
import hashlib
import requests
import json
from flask import Flask, request, redirect, url_for, render_template, session, flash, make_response
from datetime import datetime, timedelta
import pandas as pd
import io

# ==============================================================================
# KONFIGURASI WAJIB
# Ganti nilai-nilai di bawah ini dengan data Anda.
# ==============================================================================
# ID Partner dari Shopee Developer Center
PARTNER_ID = 0  # GANTI DENGAN PARTNER ID ANDA

# Kunci Partner dari Shopee Developer Center
PARTNER_KEY = "GANTI_DENGAN_PARTNER_KEY_ANDA"

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

    path_info = "/api/v2/shop/get_shop_info"
    info_data, error = call_shopee_api(path_info, shop_id=int(shop_id_str), access_token=access_token)
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
    Dispatcher untuk menangani ekspor data ke Excel berdasarkan data_type.
    """
    shop_id = request.form.get('shop_id')
    data_type = request.form.get('data_type')
    
    shop_data = session.get('shops', {}).get(shop_id)
    if not shop_data:
        flash(f"Toko dengan ID {shop_id} tidak ditemukan di sesi ini.", 'danger')
        return redirect(url_for('dashboard'))
    
    access_token = shop_data['access_token']
    df = pd.DataFrame() # DataFrame kosong sebagai default

    try:
        # --- DISPATCHER LOGIC ---
        if data_type == 'orders':
            # 1. Ambil Parameter Tanggal
            date_from_str = request.form.get('date_from')
            date_to_str = request.form.get('date_to')
            time_from = int(datetime.strptime(date_from_str, '%Y-%m-%d').timestamp())
            # Tambah 1 hari ke date_to untuk mencakup seluruh hari tersebut
            time_to = int((datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)).timestamp())

            # 2. Ambil semua Order SN dengan paginasi cursor
            all_order_sn_list = []
            cursor = ""
            while True:
                order_list_body = {
                    "time_range_field": "create_time",
                    "time_from": time_from,
                    "time_to": time_to,
                    "page_size": 100,
                    "cursor": cursor
                }
                response, error = call_shopee_api("/api/v2/order/get_order_list", shop_id=shop_id, access_token=access_token, body=order_list_body)
                if error:
                    raise Exception(f"Gagal mengambil daftar pesanan: {error}")
                
                order_list = response.get('response', {}).get('order_list', [])
                for order in order_list:
                    all_order_sn_list.append(order['order_sn'])
                
                if not response.get('response', {}).get('more', False):
                    break
                cursor = response.get('response', {}).get('next_cursor', "")

            # 3. Ambil detail pesanan dalam batch
            detailed_orders = []
            if all_order_sn_list:
                for i in range(0, len(all_order_sn_list), 50):
                    batch = all_order_sn_list[i:i+50]
                    detail_body = {"order_sn_list": batch}
                    response, error = call_shopee_api("/api/v2/order/get_order_detail", shop_id=shop_id, access_token=access_token, body=detail_body)
                    if error:
                        app.logger.error(f"Gagal mengambil detail untuk batch: {error}")
                        continue # Lanjutkan ke batch berikutnya
                    detailed_orders.extend(response.get('response', {}).get('order_list', []))
            
            if detailed_orders:
                df = pd.json_normalize(detailed_orders, sep='_')

        elif data_type == 'products':
            # Ambil semua produk dengan paginasi offset
            all_items = []
            offset = 0
            while True:
                list_body = {
                    "offset": offset,
                    "page_size": 100,
                    "item_status": ["NORMAL", "UNLIST"]
                }
                response, error = call_shopee_api("/api/v2/product/get_item_list", shop_id=shop_id, access_token=access_token, body=list_body)
                if error:
                    raise Exception(f"Gagal mengambil daftar produk: {error}")

                item_list = response.get('response', {}).get('item', [])
                if not item_list:
                    break
                
                item_ids = [item['item_id'] for item in item_list]
                
                # Ambil detail produk per batch
                detail_body = {"item_id_list": item_ids}
                detail_response, detail_error = call_shopee_api("/api/v2/product/get_item_base_info", shop_id=shop_id, access_token=access_token, body=detail_body)
                if not detail_error:
                    all_items.extend(detail_response.get('response', {}).get('item_list', []))

                offset += 100
            
            if all_items:
                df = pd.DataFrame(all_items)

        elif data_type == 'returns':
            # Ambil semua retur dengan paginasi page_no
            all_returns = []
            page_no = 1
            while True:
                return_body = {"page_no": page_no, "page_size": 50}
                response, error = call_shopee_api("/api/v2/returns/get_return_list", shop_id=shop_id, access_token=access_token, body=return_body)
                if error:
                    raise Exception(f"Gagal mengambil daftar retur: {error}")
                
                return_list = response.get('response', {}).get('return', [])
                if not return_list:
                    break
                
                all_returns.extend(return_list)
                page_no += 1

            # Proses data retur menjadi format yang lebih mudah dibaca
            if all_returns:
                processed_returns = []
                for ret in all_returns:
                    processed_item = {
                        "Nomor Pesanan": ret.get('order_sn'),
                        "Nomor Retur": ret.get('return_sn'),
                        "Status": ret.get('status'),
                        "Alasan": ret.get('reason'),
                        "Tanggal Dibuat": datetime.fromtimestamp(ret.get('create_time')).strftime('%Y-%m-%d %H:%M:%S') if ret.get('create_time') else None,
                        "Metode Pembayaran": ret.get('payment_method'),
                        "Resi Pengembalian": ret.get('logistics', {}).get('tracking_number'),
                        "Total Pengembalian Dana": ret.get('refund_amount'),
                        "Alasan Teks dari Pembeli": ret.get('text_reason')
                    }
                    processed_returns.append(processed_item)
                df = pd.DataFrame(processed_returns)

        # --- AKHIR DISPATCHER ---

        # Cek jika tidak ada data ditemukan
        if df.empty:
            flash(f"Tidak ada data ditemukan untuk laporan '{data_type}'.", 'warning')
            return redirect(url_for('dashboard'))

        # Buat file Excel di memori
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=data_type)
        output.seek(0)
        
        # Buat nama file dinamis
        filename = f"laporan_{data_type}_{shop_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        # Kirim file untuk diunduh
        response = make_response(output.read())
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        return response

    except Exception as e:
        app.logger.error(f"Gagal mengekspor data: {e}")
        flash(f"Terjadi kesalahan saat membuat laporan: {e}", 'danger')
        return redirect(url_for('dashboard'))

# ==============================================================================
# ENTRY POINT UNTUK MENJALANKAN APLIKASI
# ==============================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
