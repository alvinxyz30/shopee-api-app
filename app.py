# -*- coding: utf-8 -*-
import os
import time
import hmac
import hashlib
import requests
import json
from flask import Flask, request, redirect, url_for, render_template, session, flash
from datetime import datetime, timedelta # Pastikan ini diimpor

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
            response = requests.post(full_url, params=params, json=body, headers=headers, timeout=20)
        else:
            response = requests.get(full_url, params={**params, **(body or {})}, headers=headers, timeout=20)
        
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
    
    # Siapkan tanggal default di sini, bukan di HTML
    today = datetime.now()
    date_to_default = today.strftime('%Y-%m-%d')
    date_from_default = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    # Kirim variabel tanggal ke template
    return render_template(
        'dashboard.html', # Pastikan nama file ini benar
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

    # Langkah 1: Tukarkan 'code' dengan 'access_token'
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

    # Langkah 2: Ambil informasi toko (termasuk nama toko)
    path_info = "/api/v2/shop/get_shop_info"
    info_data, error = call_shopee_api(path_info, shop_id=int(shop_id_str), access_token=access_token)
    shop_name = f"Toko {shop_id_str}" # Nama default jika API gagal
    if error:
        flash(f"Gagal mendapatkan info nama toko: {error}. Menggunakan ID sebagai nama.", 'warning')
    else:
        shop_name = info_data.get('response', {}).get('shop_name', shop_name)

    # Langkah 3: Simpan semua data toko ke dalam session
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

# Placeholder untuk fungsi yang belum diimplementasikan
@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    flash("Fungsi 'Lihat Data' belum diimplementasikan.", 'info')
    return redirect(url_for('dashboard'))

@app.route('/export', methods=['POST'])
def export_data():
    flash("Fungsi 'Export Excel' belum diimplementasikan.", 'info')
    return redirect(url_for('dashboard'))

# ==============================================================================
# ENTRY POINT UNTUK MENJALANKAN APLIKASI
# ==============================================================================
if __name__ == '__main__':
    # 'debug=True' berguna untuk development, tapi matikan saat produksi
    app.run(host='0.0.0.0', port=5001, debug=True)
