from flask import Flask, redirect
import time
import hmac
import hashlib
import urllib.parse

app = Flask(__name__)

PARTNER_ID = 1175215
PARTNER_KEY = 'shpk6359494e627473757766626a516a494e79634950757676496c62656f6c4d'
REDIRECT_URL = 'https://alvinnovendra2.pythonanywhere.com/callback'
AUTH_PATH = '/api/v2/shop/auth_partner'
API_BASE_URL = 'https://partner.test-stable.shopeemobile.com'

@app.route('/')
def auth():
    timestamp = int(time.time())
    base_string = f"{PARTNER_ID}{AUTH_PATH}{timestamp}"

    sign = hmac.new(
        PARTNER_KEY.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    redirect_params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign,
        "redirect": REDIRECT_URL
    }

    query_string = urllib.parse.urlencode(redirect_params, quote_via=urllib.parse.quote)
    login_url = f"{API_BASE_URL}{AUTH_PATH}?{query_string}"

    print("Base String:", base_string)
    print("Generated Sign:", sign)
    print("Redirect URL:", login_url)

    return redirect(login_url)

if __name__ == '__main__':
    app.run(debug=True)
