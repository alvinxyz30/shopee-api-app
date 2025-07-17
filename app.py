from flask import Flask, redirect, request, session, render_template_string
import hmac
import hashlib
import time
import requests
import urllib.parse

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Ganti sesuai kebutuhan

PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovedra2.pythonanywhere.com/callback'
CALLBACK_PATH = '/callback'
AUTH_BASE_URL = 'https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner'


def generate_auth_url():
    timestamp = int(time.time())
    base_string = f"{PARTNER_ID}/api/v2/shop/auth_partner{timestamp}{REDIRECT_URL}"
    sign = hmac.new(
        PARTNER_KEY.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    query = {
        'partner_id': PARTNER_ID,
        'timestamp': timestamp,
        'sign': sign,
        'redirect': REDIRECT_URL
    }
    url = f"{AUTH_BASE_URL}?{urllib.parse.urlencode(query)}"
    return url


@app.route('/')
def index():
    return render_template_string('''
        <html>
        <head><title>Login Shopee</title></head>
        <body style="font-family: Arial;">
            <h2>Login Shopee</h2>
            <a href="/login"><button>Login dengan Shopee</button></a>
            {% if shop_name %}
                <p style="color: green;">Berhasil login sebagai: <strong>{{ shop_name }}</strong></p>
            {% endif %}
        </body>
        </html>
    ''', shop_name=session.get('shop_name'))


@app.route('/login')
def login():
    auth_url = generate_auth_url()
    return redirect(auth_url)


@app.route(CALLBACK_PATH)
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')
    timestamp = int(time.time())

    token_path = '/api/v2/auth/token/get'
    base_string = f"{PARTNER_ID}{token_path}{timestamp}{code}"
    sign = hmac.new(
        PARTNER_KEY.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    token_url = f"https://partner.test-stable.shopeemobile.com{token_path}"
    payload = {
        'code': code,
        'partner_id': PARTNER_ID,
        'timestamp': timestamp,
        'sign': sign
    }
    response = requests.post(token_url, json=payload)
    token_data = response.json()

    if 'access_token' in token_data.get('data', {}):
        access_token = token_data['data']['access_token']
        session['access_token'] = access_token
        session['shop_id'] = token_data['data']['shop_id']

        # Get shop detail
        detail_timestamp = int(time.time())
        detail_path = '/api/v2/shop/get_shop_info'
        base_string = f"{PARTNER_ID}{detail_path}{detail_timestamp}{access_token}{session['shop_id']}"
        detail_sign = hmac.new(
            PARTNER_KEY.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        detail_url = f"https://partner.test-stable.shopeemobile.com{detail_path}"
        headers = {'Content-Type': 'application/json'}
        params = {
            'partner_id': PARTNER_ID,
            'timestamp': detail_timestamp,
            'access_token': access_token,
            'shop_id': session['shop_id'],
            'sign': detail_sign
        }
        detail_resp = requests.get(detail_url, headers=headers, params=params)
        shop_info = detail_resp.json()

        session['shop_name'] = shop_info.get('data', {}).get('shop_name', 'Unknown')

        return redirect('/')
    else:
        return f"Gagal mendapatkan access token: {token_data}"


if __name__ == '__main__':
    app.run(debug=True)
