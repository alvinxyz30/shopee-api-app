from flask import Flask, redirect, request
import time
import hmac
import hashlib
import urllib.parse
import logging

app = Flask(__name__)

# Konfigurasi (sandbox)
PARTNER_ID = "1175215"
PARTNER_KEY = "shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d"
REDIRECT_URL = "https://alvinnovendra2.pythonanywhere.com/callback"
API_BASE_URL = "https://partner.test-stable.shopeemobile.com"

# Logging
logging.basicConfig(level=logging.INFO)

@app.route("/")
def index():
    # 1. Buat timestamp saat ini
    timestamp = int(time.time())
    logging.info(f"Timestamp: {timestamp}")

    # 2. Buat base string untuk signature
    base_string = f"{PARTNER_ID}/shop/auth_partner{timestamp}"
    logging.info(f"Base string: {base_string}")

    # 3. Generate HMAC SHA256 signature
    sign = hmac.new(
        PARTNER_KEY.encode(),
        base_string.encode(),
        hashlib.sha256
    ).hexdigest()
    logging.info(f"Generated sign: {sign}")

    # 4. Buat URL Shopee login OAuth
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign,
        "redirect": REDIRECT_URL
    }
    query_string = urllib.parse.urlencode(params)
    login_url = f"{API_BASE_URL}/api/v2/shop/auth_partner?{query_string}"
    logging.info(f"Redirecting to Shopee login: {login_url}")

    # 5. Redirect user ke Shopee
    return redirect(login_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    shop_id = request.args.get("shop_id")
    logging.info(f"Callback received: code={code}, shop_id={shop_id}")
    return f"Callback berhasil! Code: {code}, Shop ID: {shop_id}"

if __name__ == "__main__":
    app.run(debug=True)
