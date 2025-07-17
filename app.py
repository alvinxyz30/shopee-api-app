from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import os
import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
import time
import json

from shopee_api import ShopeeAPI, ShopeeAPIError
from utils import (
    validate_date_range, flatten_order_data, flatten_product_data, 
    flatten_return_data, export_to_excel, validate_shop_limit,
    sanitize_filename, convert_timestamp_to_datetime
)

# In-memory storage
shops_data = {}
api_logs = []
data_exports = {}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')

# Initialize Shopee API
shopee_api = ShopeeAPI(
    partner_id=os.environ.get('SHOPEE_PARTNER_ID', 'your_partner_id'),
    partner_key=os.environ.get('SHOPEE_PARTNER_KEY', 'your_partner_key'),
    base_url=os.environ.get('SHOPEE_BASE_URL', 'https://partner.test-stable.shopeemobile.com')
)

# Template filters
@app.template_filter('timestamp_to_date')
def timestamp_to_date_filter(timestamp):
    """Convert timestamp to readable date"""
    return convert_timestamp_to_datetime(timestamp)

# Mock Shop class for in-memory storage
class MockShop:
    def __init__(self, shop_id, shop_name, access_token, refresh_token, expires_in):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
    
    @property
    def is_token_valid(self):
        if not self.access_token:
            return False
        expires_at = self.updated_at + timedelta(seconds=self.expires_in)
        return datetime.now() < expires_at
    
    @property
    def token_expires_soon(self):
        if not self.access_token:
            return False
        expires_at = self.updated_at + timedelta(seconds=self.expires_in)
        return datetime.now() + timedelta(hours=24) > expires_at

@app.route('/')
def index():
    """Homepage - menampilkan daftar toko"""
    try:
        shops = [shop for shop in shops_data.values() if shop.is_active]
        return render_template('index.html', shops=shops)
    except Exception as e:
        app.logger.error(f"Error loading homepage: {str(e)}")
        flash('Terjadi kesalahan saat memuat halaman', 'error')
        return render_template('index.html', shops=[])

@app.route('/add_shop')
def add_shop():
    """Form untuk menambah toko baru"""
    try:
        # Cek batas maksimal toko
        shop_count = len([shop for shop in shops_data.values() if shop.is_active])
        if not validate_shop_limit(shop_count):
            flash('Maksimal 10 toko yang dapat ditambahkan', 'error')
            return redirect(url_for('index'))
        
        return render_template('add_shop.html')
    except Exception as e:
        app.logger.error(f"Error loading add shop page: {str(e)}")
        flash('Terjadi kesalahan saat memuat halaman', 'error')
        return redirect(url_for('index'))

@app.route('/auth_shop', methods=['POST'])
def auth_shop():
    """Proses autentikasi toko"""
    try:
        shop_account = request.form.get('shop_account', '').strip()
        shop_password = request.form.get('shop_password', '').strip()
        
        # Validasi input
        if not shop_account or not shop_password:
            flash('Shop Account dan Password harus diisi', 'error')
            return redirect(url_for('add_shop'))
        
        # Generate auth URL
        redirect_url = os.environ.get('SHOPEE_REDIRECT_URL', 'https://yourdomain.com/auth_callback')
        auth_url = shopee_api.generate_auth_url(redirect_url)
        
        # Simpan credentials sementara di session (dalam production gunakan cache/redis)
        # Untuk sekarang kita redirect langsung ke auth URL
        flash(f'Silakan login dengan credentials: {shop_account}', 'info')
        return redirect(auth_url)
        
    except ShopeeAPIError as e:
        app.logger.error(f"Shopee API error during auth: {str(e)}")
        flash(f'Error API Shopee: {str(e)}', 'error')
        return redirect(url_for('add_shop'))
    except Exception as e:
        app.logger.error(f"Error during shop auth: {str(e)}")
        flash('Terjadi kesalahan saat proses autentikasi', 'error')
        return redirect(url_for('add_shop'))

@app.route('/auth_callback')
def auth_callback():
    """Callback setelah OAuth authorization"""
    try:
        # Ambil code dan shop_id dari query string
        code = request.args.get('code')
        shop_id = request.args.get('shop_id')
        error = request.args.get('error')
        
        if error:
            flash(f'Authorization error: {error}', 'error')
            return redirect(url_for('add_shop'))
        
        if not code or not shop_id:
            flash('Missing authorization code atau shop_id', 'error')
            return redirect(url_for('add_shop'))
        
        # Tukar code dengan access token
        token_response = shopee_api.get_access_token(code, shop_id)
        
        access_token = token_response.get('access_token')
        refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 14400)  # Default 4 jam
        
        if not access_token or not refresh_token:
            flash('Gagal mendapatkan access token', 'error')
            return redirect(url_for('add_shop'))
        
        # Ambil info toko
        shop_info = shopee_api.get_shop_info(access_token, shop_id)
        shop_name = shop_info.get('shop_name', f'Shop {shop_id}')
        
        # Cek apakah toko sudah ada
        if shop_id in shops_data:
            # Update token yang sudah ada
            shops_data[shop_id].access_token = access_token
            shops_data[shop_id].refresh_token = refresh_token
            shops_data[shop_id].expires_in = expires_in
            shops_data[shop_id].shop_name = shop_name
            shops_data[shop_id].updated_at = datetime.now()
            shops_data[shop_id].is_active = True
            flash(f'Toko {shop_name} berhasil diperbarui', 'success')
        else:
            # Buat record toko baru
            new_shop = MockShop(
                shop_id=shop_id,
                shop_name=shop_name,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in
            )
            shops_data[shop_id] = new_shop
            flash(f'Toko {shop_name} berhasil ditambahkan', 'success')
        
        return redirect(url_for('index'))
        
    except ShopeeAPIError as e:
        app.logger.error(f"Shopee API error in callback: {str(e)}")
        flash(f'Error API Shopee: {str(e)}', 'error')
        return redirect(url_for('add_shop'))
    except Exception as e:
        app.logger.error(f"Error in auth callback: {str(e)}")
        flash('Terjadi kesalahan saat proses callback', 'error')
        return redirect(url_for('add_shop'))

@app.route('/shop/<shop_id>')
def shop_detail(shop_id):
    """Detail toko dan pilihan data"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            flash('Toko tidak ditemukan', 'error')
            return redirect(url_for('index'))
        
        # Cek status token
        token_status = 'valid' if shop.is_token_valid else 'expired'
        if shop.token_expires_soon:
            token_status = 'expires_soon'
        
        return render_template('shop_detail.html', shop=shop, token_status=token_status)
        
    except Exception as e:
        app.logger.error(f"Error loading shop detail: {str(e)}")
        flash('Terjadi kesalahan saat memuat detail toko', 'error')
        return redirect(url_for('index'))

@app.route('/shop/<shop_id>/orders')
def view_orders(shop_id):
    """View daftar order dengan pagination"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            shop = None
        if not shop:
            flash('Toko tidak ditemukan', 'error')
            return redirect(url_for('index'))
        
        if not shop.is_token_valid:
            flash('Token toko sudah expired, silakan login ulang', 'error')
            return redirect(url_for('shop_detail', shop_id=shop_id))
        
        page = request.args.get('page', 1, type=int)
        per_page = app.config['ORDERS_PER_PAGE']
        
        # Default range: 7 hari terakhir
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        # Override jika ada parameter tanggal
        if request.args.get('date_from'):
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
        if request.args.get('date_to'):
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
        
        # Convert ke timestamp
        time_from = int(date_from.timestamp())
        time_to = int(date_to.timestamp())
        
        # Ambil data dari Shopee API
        orders_response = shopee_api.get_order_list(
            shop.access_token, shop_id, time_from, time_to, per_page
        )
        
        order_list = orders_response.get('response', {}).get('order_list', [])
        
        # Jika ada order, ambil detail lengkap
        orders_data = []
        if order_list:
            order_sns = [order['order_sn'] for order in order_list]
            
            # Split menjadi chunks of 50 (limit API)
            for i in range(0, len(order_sns), 50):
                chunk = order_sns[i:i+50]
                detail_response = shopee_api.get_order_detail(shop.access_token, shop_id, chunk)
                order_details = detail_response.get('response', {}).get('order_list', [])
                orders_data.extend(order_details)
        
        # Pagination manual (karena API Shopee menggunakan cursor)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_orders = orders_data[start_idx:end_idx]
        
        # Hitung total pages
        total_orders = len(orders_data)
        total_pages = (total_orders + per_page - 1) // per_page
        
        return render_template('orders.html', 
                             shop=shop,
                             orders=paginated_orders,
                             page=page,
                             total_pages=total_pages,
                             total_orders=total_orders,
                             date_from=date_from.strftime('%Y-%m-%d'),
                             date_to=date_to.strftime('%Y-%m-%d'))
        
    except ShopeeAPIError as e:
        app.logger.error(f"Shopee API error loading orders: {str(e)}")
        flash(f'Error API Shopee: {str(e)}', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))
    except Exception as e:
        app.logger.error(f"Error loading orders: {str(e)}")
        flash('Terjadi kesalahan saat memuat data order', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))

@app.route('/shop/<shop_id>/products')
def view_products(shop_id):
    """View daftar produk dengan pagination"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            shop = None
        if not shop:
            flash('Toko tidak ditemukan', 'error')
            return redirect(url_for('index'))
        
        if not shop.is_token_valid:
            flash('Token toko sudah expired, silakan login ulang', 'error')
            return redirect(url_for('shop_detail', shop_id=shop_id))
        
        page = request.args.get('page', 1, type=int)
        per_page = app.config['PRODUCTS_PER_PAGE']
        offset = (page - 1) * per_page
        
        # Ambil daftar produk
        products_response = shopee_api.get_item_list(
            shop.access_token, shop_id, offset, per_page
        )
        
        item_list = products_response.get('response', {}).get('item', [])
        total_count = products_response.get('response', {}).get('total_count', 0)
        
        # Ambil detail produk jika ada
        products_data = []
        if item_list:
            item_ids = [item['item_id'] for item in item_list]
            
            # Split menjadi chunks of 50 (limit API)
            for i in range(0, len(item_ids), 50):
                chunk = item_ids[i:i+50]
                detail_response = shopee_api.get_item_base_info(shop.access_token, shop_id, chunk)
                product_details = detail_response.get('response', {}).get('item_list', [])
                products_data.extend(product_details)
        
        # Hitung pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        return render_template('products.html',
                             shop=shop,
                             products=products_data,
                             page=page,
                             total_pages=total_pages,
                             total_products=total_count)
        
    except ShopeeAPIError as e:
        app.logger.error(f"Shopee API error loading products: {str(e)}")
        flash(f'Error API Shopee: {str(e)}', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))
    except Exception as e:
        app.logger.error(f"Error loading products: {str(e)}")
        flash('Terjadi kesalahan saat memuat data produk', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))

@app.route('/shop/<shop_id>/returns')
def view_returns(shop_id):
    """View daftar return dengan pagination"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            shop = None
        if not shop:
            flash('Toko tidak ditemukan', 'error')
            return redirect(url_for('index'))
        
        if not shop.is_token_valid:
            flash('Token toko sudah expired, silakan login ulang', 'error')
            return redirect(url_for('shop_detail', shop_id=shop_id))
        
        page = request.args.get('page', 1, type=int)
        per_page = app.config['RETURNS_PER_PAGE']
        
        # Default range: 30 hari terakhir
        date_to = datetime.now()
        date_from = date_to - timedelta(days=30)
        
        # Override jika ada parameter tanggal
        if request.args.get('date_from'):
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
        if request.args.get('date_to'):
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
        
        # Convert ke timestamp
        time_from = int(date_from.timestamp())
        time_to = int(date_to.timestamp())
        
        # Ambil data return dari API
        returns_response = shopee_api.get_return_list(
            shop.access_token, shop_id, page, per_page, time_from, time_to
        )
        
        return_list = returns_response.get('response', {}).get('return_list', [])
        total_count = returns_response.get('response', {}).get('total_count', 0)
        
        # Ambil detail return jika ada
        returns_data = []
        if return_list:
            return_sns = [ret['return_sn'] for ret in return_list]
            
            # Split menjadi chunks of 50 (limit API)
            for i in range(0, len(return_sns), 50):
                chunk = return_sns[i:i+50]
                detail_response = shopee_api.get_return_detail(shop.access_token, shop_id, chunk)
                return_details = detail_response.get('response', {}).get('return_list', [])
                returns_data.extend(return_details)
        
        # Hitung pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        return render_template('returns.html',
                             shop=shop,
                             returns=returns_data,
                             page=page,
                             total_pages=total_pages,
                             total_returns=total_count,
                             date_from=date_from.strftime('%Y-%m-%d'),
                             date_to=date_to.strftime('%Y-%m-%d'))
        
    except ShopeeAPIError as e:
        app.logger.error(f"Shopee API error loading returns: {str(e)}")
        flash(f'Error API Shopee: {str(e)}', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))
    except Exception as e:
        app.logger.error(f"Error loading returns: {str(e)}")
        flash('Terjadi kesalahan saat memuat data return', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))

@app.route('/export/<shop_id>/<data_type>')
def export_data(shop_id, data_type):
    """Export data ke Excel"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            shop = None
        if not shop:
            return jsonify({'error': 'Toko tidak ditemukan'}), 404
        
        if not shop.is_token_valid:
            return jsonify({'error': 'Token toko sudah expired'}), 401
        
        # Validasi data type
        if data_type not in ['orders', 'products', 'returns']:
            return jsonify({'error': 'Tipe data tidak valid'}), 400
        
        # Ambil parameter tanggal
        date_from_str = request.args.get('date_from')
        date_to_str = request.args.get('date_to')
        
        # Buat record export
        date_from = date_to = None
        if date_from_str and date_to_str:
            date_from, date_to = validate_date_range(date_from_str, date_to_str, 365)
        
        export_record = create_export_record(shop_id, data_type, date_from, date_to)
        
        # Export data sesuai tipe
        if data_type == 'orders':
            exported_file = export_orders_data(shop, date_from, date_to)
        elif data_type == 'products':
            exported_file = export_products_data(shop)
        elif data_type == 'returns':
            exported_file = export_returns_data(shop, date_from, date_to)
        
        # Update record export
        update_export_record(export_record.id, 0, exported_file, 'completed')
        
        # Return file untuk download
        return send_file(exported_file, as_attachment=True)
        
    except Exception as e:
        app.logger.error(f"Error exporting data: {str(e)}")
        return jsonify({'error': f'Gagal export data: {str(e)}'}), 500

def export_orders_data(shop, date_from=None, date_to=None):
    """Export data orders ke Excel"""
    if not date_from or not date_to:
        date_to = datetime.now()
        date_from = date_to - timedelta(days=30)
    
    time_from = int(date_from.timestamp())
    time_to = int(date_to.timestamp())
    
    all_orders = []
    cursor = ""
    
    # Ambil semua data dengan pagination
    while True:
        orders_response = shopee_api.get_order_list(
            shop.access_token, shop.shop_id, time_from, time_to, 100, cursor
        )
        
        order_list = orders_response.get('response', {}).get('order_list', [])
        if not order_list:
            break
        
        # Ambil detail orders
        order_sns = [order['order_sn'] for order in order_list]
        for i in range(0, len(order_sns), 50):
            chunk = order_sns[i:i+50]
            detail_response = shopee_api.get_order_detail(shop.access_token, shop.shop_id, chunk)
            order_details = detail_response.get('response', {}).get('order_list', [])
            all_orders.extend(order_details)
        
        # Cek apakah ada data lagi
        cursor = orders_response.get('response', {}).get('next_cursor', "")
        if not cursor:
            break
    
    # Flatten data untuk Excel
    flattened_data = [flatten_order_data(order) for order in all_orders]
    
    # Generate filename
    filename = sanitize_filename(f"orders_{shop.shop_name}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.xlsx")
    
    # Export ke Excel
    return export_to_excel(flattened_data, filename, 'Orders')

def export_products_data(shop):
    """Export data products ke Excel"""
    all_products = []
    offset = 0
    page_size = 100
    
    # Ambil semua produk dengan pagination
    while True:
        products_response = shopee_api.get_item_list(
            shop.access_token, shop.shop_id, offset, page_size
        )
        
        item_list = products_response.get('response', {}).get('item', [])
        if not item_list:
            break
        
        # Ambil detail produk
        item_ids = [item['item_id'] for item in item_list]
        for i in range(0, len(item_ids), 50):
            chunk = item_ids[i:i+50]
            detail_response = shopee_api.get_item_base_info(shop.access_token, shop.shop_id, chunk)
            product_details = detail_response.get('response', {}).get('item_list', [])
            all_products.extend(product_details)
        
        # Next page
        offset += page_size
        
        # Break jika hasil kurang dari page_size (tidak ada data lagi)
        if len(item_list) < page_size:
            break
    
    # Flatten data untuk Excel
    flattened_data = [flatten_product_data(product) for product in all_products]
    
    # Generate filename
    filename = sanitize_filename(f"products_{shop.shop_name}_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    # Export ke Excel
    return export_to_excel(flattened_data, filename, 'Products')

def export_returns_data(shop, date_from=None, date_to=None):
    """Export data returns ke Excel"""
    if not date_from or not date_to:
        date_to = datetime.now()
        date_from = date_to - timedelta(days=90)
    
    time_from = int(date_from.timestamp())
    time_to = int(date_to.timestamp())
    
    all_returns = []
    page = 1
    page_size = 100
    
    # Ambil semua data return dengan pagination
    while True:
        returns_response = shopee_api.get_return_list(
            shop.access_token, shop.shop_id, page, page_size, time_from, time_to
        )
        
        return_list = returns_response.get('response', {}).get('return_list', [])
        if not return_list:
            break
        
        # Ambil detail return
        return_sns = [ret['return_sn'] for ret in return_list]
        for i in range(0, len(return_sns), 50):
            chunk = return_sns[i:i+50]
            detail_response = shopee_api.get_return_detail(shop.access_token, shop.shop_id, chunk)
            return_details = detail_response.get('response', {}).get('return_list', [])
            all_returns.extend(return_details)
        
        # Next page
        page += 1
        
        # Break jika hasil kurang dari page_size (tidak ada data lagi)
        if len(return_list) < page_size:
            break
    
    # Flatten data untuk Excel
    flattened_data = [flatten_return_data(return_data) for return_data in all_returns]
    
    # Generate filename
    filename = sanitize_filename(f"returns_{shop.shop_name}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.xlsx")
    
    # Export ke Excel
    return export_to_excel(flattened_data, filename, 'Returns')

@app.route('/delete_shop/<shop_id>', methods=['POST'])
def delete_shop(shop_id):
    """Hapus toko (soft delete)"""
    try:
        shop = shops_data.get(shop_id)
        if shop:
            shop.is_active = False
            # Shop updated in memory
            flash(f'Toko {shop.shop_name} berhasil dihapus', 'success')
        else:
            flash('Toko tidak ditemukan', 'error')
    except Exception as e:
        app.logger.error(f"Error deleting shop: {str(e)}")
        flash('Terjadi kesalahan saat menghapus toko', 'error')
    
    return redirect(url_for('index'))

@app.route('/api_logs/<shop_id>')
def api_logs(shop_id):
    """View API logs untuk debugging"""
    try:
        shop = shops_data.get(shop_id)
        if not shop or not shop.is_active:
            shop = None
        if not shop:
            flash('Toko tidak ditemukan', 'error')
            return redirect(url_for('index'))
        
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Filter logs untuk shop tertentu
        shop_logs = [log for log in api_logs if log.get('shop_id') == shop_id]
        shop_logs.sort(key=lambda x: x.get('created_at', datetime.now()), reverse=True)
        
        # Simple pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated_logs = shop_logs[start:end]
        
        # Mock pagination object
        class MockPagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
        
        logs = MockPagination(paginated_logs, page, per_page, len(shop_logs))
        
        return render_template('api_logs.html', shop=shop, logs=logs)
        
    except Exception as e:
        app.logger.error(f"Error loading API logs: {str(e)}")
        flash('Terjadi kesalahan saat memuat log API', 'error')
        return redirect(url_for('shop_detail', shop_id=shop_id))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)