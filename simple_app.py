from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import logging
from datetime import datetime, timedelta
import json
from shopee_api import ShopeeAPI, ShopeeAPIError

# Setup logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'simple-secret-key'

# In-memory storage (reset setiap restart)
shops_data = {}
api_logs = []

# Initialize Shopee API dengan config manual
shopee_api = ShopeeAPI(
    partner_id="your_partner_id",  # Ganti dengan partner_id asli
    partner_key="your_partner_key",  # Ganti dengan partner_key asli
    base_url="https://partner.test-stable.shopeemobile.com"
)

@app.route('/')
def index():
    return render_template('simple_index.html', shops=list(shops_data.values()))

@app.route('/add_shop')
def add_shop():
    return render_template('simple_add_shop.html')

@app.route('/auth_shop', methods=['POST'])
def auth_shop():
    try:
        shop_name = request.form.get('shop_name', 'Test Shop')
        redirect_url = "https://yourdomain.com/auth_callback"
        
        auth_url = shopee_api.generate_auth_url(redirect_url)
        flash(f'Auth URL generated for {shop_name}', 'success')
        
        return redirect(auth_url)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('add_shop'))

@app.route('/auth_callback')
def auth_callback():
    try:
        code = request.args.get('code')
        shop_id = request.args.get('shop_id')
        
        if not code or not shop_id:
            flash('Missing authorization code or shop_id', 'error')
            return redirect(url_for('index'))
        
        # Get access token
        token_data = shopee_api.get_access_token(code, shop_id)
        
        # Save to memory
        shops_data[shop_id] = {
            'shop_id': shop_id,
            'shop_name': f'Shop {shop_id}',
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'expires_in': token_data['expires_in'],
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        flash(f'Shop {shop_id} berhasil diauthorize!', 'success')
        return redirect(url_for('shop_detail', shop_id=shop_id))
        
    except Exception as e:
        flash(f'Authorization failed: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/shop/<shop_id>')
def shop_detail(shop_id):
    shop = shops_data.get(shop_id)
    if not shop:
        flash('Shop not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('simple_shop_detail.html', shop=shop)

@app.route('/api/shop/<shop_id>/orders')
def get_orders(shop_id):
    try:
        shop = shops_data.get(shop_id)
        if not shop:
            return jsonify({'error': 'Shop not found'}), 404
        
        orders = shopee_api.get_order_list(
            shop_id=shop_id,
            access_token=shop['access_token']
        )
        
        return jsonify({'orders': orders})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)