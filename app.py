from flask import Flask, redirect
import hashlib
import hmac
import time
import urllib.parse
import logging

app = Flask(__name__)

# === CONFIG ===
PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovendra2.pythonanywhere.com'
HOST = 'https://partner.test-stable.shopeemobile.com'
PATH = '/api/v2/shop/auth_partner'

logging.basicConfig(level=logging.INFO)


def generate_sign(partner_id, path, timestamp, partner_key):
    base_string = f"{partner_id}{path}{timestamp}"
    logging.info(f"Base string: {base_string}")
    sign = hmac.new(
        partner_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    logging.info(f"Generated sign: {sign}")
    return sign


@app.route('/')
def auth():
    timestamp = int(time.time())
    sign = generate_sign(PARTNER_ID, PATH, timestamp, PARTNER_KEY)
    redirect_url_encoded = urllib.parse.quote(REDIRECT_URL, safe='')

    auth_url = (
        f"{HOST}{PATH}"
        f"?partner_id={PARTNER_ID}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&redirect={redirect_url_encoded}"
    )

    logging.info(f"Redirect URL: {auth_url}")
    return redirect(auth_url)


@app.route('/callback')
def callback():
    return "✅ Callback received!"


if __name__ == '__main__':
    app.run(debug=True)
