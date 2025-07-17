from flask import Flask, redirect, request, session, render_template_string
import hmac
import hashlib
import time
import requests
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Partner info (sandbox)
PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovedra2.pythonanywhere.com/callback'
CALLBACK_PATH = '/callback'

# OAuth authorize endpoint for Shopee Open Platform
AUTH_URL = 'https://open.sandbox.test-stable.shopee.com/authorize'

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
    timestamp = int(time.time())
    redirect_uri_encoded = urllib.parse.quote(REDIRECT_URL, safe='')

    base_string = f"{PARTNER_ID}{REDIRECT_URL}{timestamp}"
    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    params = {
        "partner_id": PARTNER_ID,
        "redirect": REDIRECT_URL,
        "timestamp": timestamp,
        "sign": sign
    }

    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    return redirect(auth_url)

@app.route(CALLBACK_PATH)
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')

    if not code or not shop_id:
        return "Missing code or shop_id in callback"

    # Exchange code for token
    timestamp = int(time.time())
    path = '/api/v2/auth/token/get'
    base_string = f"{PARTNER_ID}{path}{timestamp}{code}{shop_id}"
    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    url = f"https://partner.test-stable.shopeemobile.com{path}"
    payload = {
        "code": code,
        "shop_id": int(shop_id),
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign
    }
    headers = {'Content-Type': 'application/json'}

    res = requests.post(url, json=payload, headers=headers)
    res_data = res.json()

    if 'access_token' not in res_data.get('data', {}):
        return f"Gagal mendapatkan token: {res_data}"

    session['access_token'] = res_data['data']['access_token']
    session['shop_id'] = shop_id

    # Get shop info
    timestamp = int(time.time())
    path = '/api/v2/shop/get_shop_info'
    base_string = f"{PARTNER_ID}{path}{timestamp}{session['access_token']}{shop_id}"
    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    url = f"https://partner.test-stable.shopeemobile.com{path}"
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "access_token": session['access_token'],
        "shop_id": shop_id,
        "sign": sign
    }

    res = requests.get(url, params=params)
    data = res.json()
    session['shop_name'] = data.get('data', {}).get('shop_name', 'Unknown')

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
