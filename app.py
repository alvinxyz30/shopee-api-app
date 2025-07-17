from flask import Flask, redirect, request, render_template
import time
import hashlib
import hmac
import requests

app = Flask(__name__)

# Shopee sandbox API credentials
PARTNER_ID = 1175215
PARTNER_KEY = b'shpk6359494e627473757766662a516a494e79634950757676496c62656f6c4d'
REDIRECT_URI = 'https://alvinnovedra2.pythonanywhere.com/callback'
API_HOST = 'https://partner.test-stable.shopeemobile.com'

ACCESS_TOKENS = {}

def generate_signature(path, timestamp, access_token=""):
    base_string = f"{PARTNER_ID}{path}{timestamp}{access_token}"
    return hmac.new(PARTNER_KEY, base_string.encode(), hashlib.sha256).hexdigest()

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/login')
def login():
    timestamp = int(time.time())
    path = "/api/v2/shop/auth_partner"
    sign = generate_signature(path, timestamp)
    
    auth_url = (
        f"{API_HOST}{path}"
        f"?partner_id={PARTNER_ID}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&redirect={REDIRECT_URI}"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')
    timestamp = int(time.time())
    path = "/api/v2/auth/token/get"
    sign = generate_signature(path, timestamp)

    headers = {"Content-Type": "application/json"}
    payload = {
        "code": code,
        "shop_id": int(shop_id),
        "partner_id": PARTNER_ID,
        "sign": sign,
        "timestamp": timestamp
    }

    response = requests.post(API_HOST + path, json=payload, headers=headers)
    token_data = response.json().get("response", {})
    access_token = token_data.get("access_token")
    
    if not access_token:
        return "Gagal mendapatkan token.", 400

    ACCESS_TOKENS[shop_id] = token_data
    return redirect(f"/shop_info?shop_id={shop_id}")

@app.route('/shop_info')
def shop_info():
    shop_id = request.args.get('shop_id')
    token_data = ACCESS_TOKENS.get(shop_id)
    if not token_data:
        return "Access token not found.", 404

    path = "/api/v2/shop/get_shop_info"
    timestamp = int(time.time())
    access_token = token_data["access_token"]
    sign = generate_signature(path, timestamp, access_token)

    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign,
        "access_token": access_token,
        "shop_id": shop_id
    }

    response = requests.get(API_HOST + path, headers=headers, params=params)
    shop_data = response.json()

    if "response" in shop_data:
        shop_name = shop_data["response"].get("shop_name", "Tidak diketahui")
        return render_template("shop_info.html", shop_name=shop_name)
    else:
        return "Gagal mengambil data toko.", 400

if __name__ == '__main__':
    app.run(debug=True)
