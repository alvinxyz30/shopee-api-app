from flask import Flask, redirect, request, session, render_template_string
import hmac
import hashlib
import time
import requests
import urllib.parse

app = Flask(__name__)
app.secret_key = 'secret123'

# ===== CONFIGURATION =====
PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovedra2.pythonanywhere.com/callback'

# ===== MAIN UI =====
@app.route('/')
def index():
    return render_template_string('''
        <html>
        <head><title>Login Shopee Seller</title></head>
        <body style="font-family: Arial;">
            <h2>Login Shopee Seller</h2>
            <a href="/login"><button>Login dengan Shopee</button></a>
            {% if shop_name %}
                <p style="color: green;">Berhasil login sebagai: <strong>{{ shop_name }}</strong></p>
            {% endif %}
        </body>
        </html>
    ''', shop_name=session.get('shop_name'))

# ===== LOGIN: Redirect to Shopee Auth =====
@app.route('/login')
def login():
    timestamp = int(time.time())
    base_string = f"{PARTNER_ID}{REDIRECT_URL}{timestamp}"
    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    auth_url = (
        f"https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner"
        f"?partner_id={PARTNER_ID}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&redirect={urllib.parse.quote(REDIRECT_URL)}"
    )
    return redirect(auth_url)

# ===== CALLBACK: Get Token =====
@app.route('/callback')
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')

    if not code or not shop_id:
        return "Missing code or shop_id"

    # Get access token
    timestamp = int(time.time())
    path = "/api/v2/auth/token/get"
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

    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    data = res.json()

    if "access_token" not in data.get("data", {}):
        return f"Gagal ambil token: {data}"

    session['access_token'] = data['data']['access_token']
    session['shop_id'] = shop_id

    # Ambil info toko
    timestamp = int(time.time())
    path = "/api/v2/shop/get_shop_info"
    base_string = f"{PARTNER_ID}{path}{timestamp}{session['access_token']}{shop_id}"
    sign = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()

    res = requests.get(
        f"https://partner.test-stable.shopeemobile.com{path}",
        params={
            "partner_id": PARTNER_ID,
            "timestamp": timestamp,
            "access_token": session['access_token'],
            "shop_id": shop_id,
            "sign": sign
        }
    )

    shop_info = res.json()
    session['shop_name'] = shop_info.get("data", {}).get("shop_name", "Unknown")

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
