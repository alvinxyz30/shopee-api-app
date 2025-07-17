from flask import Flask, redirect
import hashlib
import hmac
import time
import urllib.parse
import logging

app = Flask(__name__)

# Konfigurasi Sandbox Shopee
PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovendra2.pythonanywhere.com'
API_HOST = 'https://partner.test-stable.shopeemobile.com'
AUTH_PATH = '/api/v2/shop/auth_partner'  # sesuai dokumentasi: harus lengkap dengan "/api/v2"

# Logging setup
logging.basicConfig(level=logging.INFO)


def generate_sign(partner_id: int, path: str, timestamp: int, partner_key: str) -> str:
    """
    Format base string untuk Public API: partner_id + path + timestamp
    """
    base_string = f"{partner_id}{path}{timestamp}"
    sign = hmac.new(
        partner_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    logging.info(f"Base string: {base_string}")
    logging.info(f"Generated sign: {sign}")
    return sign


@app.route('/')
def shopee_auth():
    timestamp = int(time.time())
    sign = generate_sign(PARTNER_ID, AUTH_PATH, timestamp, PARTNER_KEY)

    # Encode redirect_url agar valid
    encoded_redirect = urllib.parse.quote(REDIRECT_URL, safe='')

    # Compose final URL
    auth_url = (
        f"{API_HOST}{AUTH_PATH}"
        f"?partner_id={PARTNER_ID}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&redirect={encoded_redirect}"
    )

    logging.info(f"Redirecting to Shopee login: {auth_url}")
    return redirect(auth_url)


@app.route('/callback')
def callback():
    return "Callback received from Shopee"


if __name__ == '__main__':
    app.run(debug=True)
