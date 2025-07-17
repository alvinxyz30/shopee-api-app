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
# KONFIGURASI APLIKASI
# ==============================================================================
# PENTING: Ganti nilai-nilai ini dengan data Anda sebelum menjalankan.
# Jaga kerahasiaan Partner Key Anda.
PARTNER_ID = 2012002
PARTNER_KEY = "shpk715045424a75484f6b7379476f4c44444d506b4d4b6f7a6d4f544a4f6a6d"
REDIRECT_URL_DOMAIN = "https://alvinnovendra2.pythonanywhere.com" # Ganti dengan domain Anda
BASE_URL = "https://partner.shopeemobile.com"

# ==============================================================================
# INISIALISASI FLASK
# ==============================================================================
app = Flask(__name__)
# Kunci rahasia ini penting untuk keamanan session. Ganti dengan string acak Anda sendiri.
app.config['SECRET_KEY'] = '8f4a7b1e9c2d5a3b6f8e7d4c1a9b3e5f7d2c8a1b4e6f9d3c5b7a2e8f1d9c4b6a'

# ==============================================================================
# FUNGSI HELPER UNTUK SHOPEE API V2
# ==============================================================================
def generate_signature(path, timestamp, access_token=None, shop_id=None):
    """Membuat signature untuk semua jenis panggilan API V2."""
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
    
    # Validasi awal bahwa konfigurasi sudah diisi
    if not all([PARTNER_ID, PARTNER_KEY not in ["", "GANTI_DENGAN_PARTNER_KEY_PRODUKSI_ANDA"]]):
        msg = "Partner ID / Partner Key belum diatur di file konfigurasi."
        app.logger.error(msg)
        return None, msg

    sign = generate_signature(path, timestamp, access_token, shop_id)
    
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign
    }
    if access_token:
        params["access_token"] = access_token
    if shop_id:
        params["shop_id"] = shop_id

    full_url = f"{BASE_URL}{path}"
    headers = {'Content-Type': 'application/json'}

    try:
        if method.upper() == 'POST':
            response = requests.post(full_url, params=params, json=body, headers=headers, timeout=20)
        else: # GET
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
# RUTE-RUTE UTAMA APLIKASI
# ==============================================================================
@app.route('/')
def dashboard():
    """Halaman utama, menampilkan toko dari session."""
    shops = session.get('shops', {})
    return render_template('dashboard_no_db.html', shops=shops)

@app.route('/authorize')
def authorize():
    """Mengarahkan user ke halaman otorisasi Shopee."""
    path = "/api/v2/shop/auth_partner"
    sign = generate_signature(path, int(time.time()))
    redirect_full_url = f"{REDIRECT_URL_DOMAIN}{url_for('callback')}"
    
    auth_url = f"{BASE_URL}{path}?partner_id={PARTNER_ID}&redirect={redirect_full_url}&sign={sign}&timestamp={int(time.time())}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Menangani callback dan menyimpan data ke session."""
    code = request.args.get('code')
    shop_id_str = request.args.get('shop_id')

    if not code or not shop_id_str:
        flash("Callback dari Shopee tidak valid.", 'danger')
        return redirect(url_for('dashboard'))

    # 1. Tukarkan 'code' dengan 'access_token'
    path_token = "/api/v2/auth/token/get"
    body_token = {"code": code, "shop_id": int(shop_id_str)}
    token_data, error = call_shopee_api(path_token, body=body_token)

    if error:
        flash(f"Gagal mendapatkan token: {error}", 'danger')
        return redirect(url_for('dashboard'))

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expire_in = token_data.get('expire_in')

    if not all([access_token, refresh_token, expire_in]):
        flash("Respons token dari Shopee tidak lengkap.", 'danger')
        return redirect(url_for('dashboard'))

    # 2. Ambil informasi toko
    path_info = "/api/v2/shop/get_shop_info"
    info_data, error = call_shopee_api(path_info, shop_id=int(shop_id_str), access_token=access_token)
    shop_name = f"Toko {shop_id_str}"
    if error:
        flash(f"Gagal mendapatkan info nama toko: {error}. Menggunakan ID sebagai nama.", 'warning')
    else:
        shop_name = info_data.get('response', {}).get('shop_name', shop_name)

    # 3. Simpan atau update data toko di session
    # 'shops' akan disimpan sebagai dictionary, dengan shop_id sebagai key
    shops = session.get('shops', {})
    shops[shop_id_str] = {
        'shop_id': shop_id_str,
        'shop_name': shop_name,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expire_in': int(time.time()) + expire_in
    }
    session['shops'] = shops
    session.modified = True  # Pastikan session disimpan

    flash(f"Toko '{shop_name}' berhasil dihubungkan ke sesi ini.", 'success')
    return redirect(url_for('dashboard'))
    
@app.route('/clear_session')
def clear_session():
    """Menghapus semua data dari session."""
    session.clear()
    flash('Semua data sesi dan toko terhubung telah dihapus.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    """Menarik data dari API dan menampilkannya di halaman web (dengan paginasi)."""
    # Implementasi fungsi ini akan memerlukan file template view_data.html
    flash("Fungsi 'Lihat Data' belum diimplementasikan sepenuhnya dalam versi ini.", 'info')
    return redirect(url_for('dashboard'))


@app.route('/export', methods=['POST'])
def export_data():
    """Mengekspor data ke file Excel dan mengunduhnya."""
    # Implementasi fungsi ini memerlukan logika paginasi lengkap untuk menarik semua data
    flash("Fungsi 'Export Excel' belum diimplementasikan sepenuhnya dalam versi ini.", 'info')
    return redirect(url_for('dashboard'))

# ==============================================================================
# ENTRY POINT APLIKASI
# ==============================================================================
if __name__ == '__main__':
    # Jalankan aplikasi Flask
    # host='0.0.0.0' agar bisa diakses dari jaringan lokal
    app.run(host='0.0.0.0', port=5001, debug=True)

