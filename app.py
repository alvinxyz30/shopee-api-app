from flask import Flask, redirect, request, session, render_template_string
import hmac
import hashlib
import time
import requests
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Ganti sesuai kebutuhan

PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovedra2.pythonanywhere.com/callback'
CALLBACK_PATH = '/callback'

# Generate the correct OAuth2 authorization URL using newer flow
def generate_auth_url():
    timestamp = int(time.time())
    next_url = f"https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner?isRedirect=true"

    state = {
        "nonce": "some_random_string",  # Bisa random UUID juga
        "id": PARTNER_ID,
        "auth_shop": 1,
        "next_url": next_url,
        "is_auth": 0
    }

    state_json = json.dumps(state, separators=(',', ':'))
    encoded_state = urllib.parse.quote(state_json)

    # Create base string
    base_string = f"client_id=dfc11909fd05496491c33433d61b7020&lang=en&login_types=[1,4,2]&max_auth_age=3600&redirect_uri=https://open.sandbox.test-stable.shopee.com/api/v1/oauth2/callback&region=SG&required_passwd=true&respond_code=code&scope=profile&state={encoded_state}&timestamp={timestamp}&title=sla_title_open_platform_app_login"

    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    oauth_url = (
        f"https://account.sandbox.test-stable.shopee.com/signin/oauth/accountchooser?"
        f"client_id=dfc11909fd05496491c33433d61b7020&lang=en&login_types=%5B1%2C4%2C2%5D&max_auth_age=3600"
        f"&redirect_uri=https%3A%2F%2Fopen.sandbox.test-stable.shopee.com%2Fapi%2Fv1%2Foauth2%2Fcallback&region=SG"
        f"&required_passwd=true&respond_code=code&scope=profile&state={encoded_state}"
        f"&timestamp={timestamp}&title=sla_title_open_platform_app_login&sign={sign}"
    )
    return oauth_url

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

    token_url = f"https://partner.test-stable.shopeeemobile.com{token_path}"
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

        detail_url = f"https://partner.test-stable.shopeeemobile.com{detail_path}"
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
