from flask import Flask, redirect, request, session, render_template
import hashlib, hmac, time, requests, os, logging

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

PARTNER_ID = 1175215
PARTNER_KEY = 'shpk455a5a728a2-xxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # ganti dengan key asli kamu
API_BASE_URL = 'https://partner.test-stable.shopeemobile.com/api/v2'
REDIRECT_URL = 'https://alvinnovendra2.pythonanywhere.com/callback'

# Logging setup
logging.basicConfig(filename="shopee_oauth.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def gen_signature(path, timestamp):
    base_string = f"{PARTNER_ID}{path}{timestamp}"
    signature = hmac.new(PARTNER_KEY.encode(), base_string.encode(), hashlib.sha256).hexdigest()
    logging.info(f"Base string: {base_string}")
    logging.info(f"Generated sign: {signature}")
    return signature

@app.route('/')
def index():
    if 'access_token' in session:
        return render_template('index.html', logged_in=True)
    return render_template('index.html', logged_in=False)

@app.route('/login')
def login():
    timestamp = int(time.time())
    path = '/shop/auth_partner'
    sign = gen_signature(path, timestamp)

    login_url = (
        f"{API_BASE_URL}{path}"
        f"?partner_id={PARTNER_ID}&timestamp={timestamp}&sign={sign}&redirect={REDIRECT_URL}"
    )
    logging.info(f"Redirecting to Shopee login: {login_url}")
    return redirect(login_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')
    timestamp = int(time.time())
    path = '/auth/token/get'
    sign = gen_signature(path, timestamp)

    payload = {
        'code': code,
        'shop_id': int(shop_id),
        'partner_id': PARTNER_ID,
        'sign': sign,
        'timestamp': timestamp
    }

    logging.info(f"Callback payload: {payload}")

    try:
        res = requests.post(API_BASE_URL + path, json=payload)
        res_json = res.json()
        logging.info(f"Token response: {res_json}")

        if 'access_token' in res_json:
            session['access_token'] = res_json['access_token']
            session['shop_id'] = shop_id
            return redirect('/')
        else:
            return f"Token Error: {res_json}", 400
    except Exception as e:
        logging.exception("Exception during token retrieval")
        return f"Internal Error: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
