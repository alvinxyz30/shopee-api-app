from flask import Flask, request, redirect, session, render_template, send_file
import time
import hashlib
import requests
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'random_secret_key'

# ========== KONFIGURASI ==========
PARTNER_ID = 1175215
PARTNER_KEY = 'shpk455a5a6364684f774d745463694e6669564878566a7a466a4b6558507648'
REDIRECT_URL = 'https://alvinnovendra2.pythonanywhere.com/callback'
API_BASE_URL = 'https://partner.test-stable.shopeemobile.com/api/v2'

# ========== UTIL ==========
def gen_signature(path, timestamp):
    base_string = f"{PARTNER_ID}{path}{timestamp}{PARTNER_KEY}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def shopee_post(path, payload):
    timestamp = int(time.time())
    sign = gen_signature(path, timestamp)
    payload.update({
        'partner_id': PARTNER_ID,
        'timestamp': timestamp,
        'sign': sign
    })
    url = API_BASE_URL + path
    return requests.post(url, json=payload).json()

# ========== ROUTES ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    timestamp = int(time.time())
    path = '/shop/auth_partner'
    sign = gen_signature('/api/v2' + path, timestamp)
    url = f"{API_BASE_URL}{path}?partner_id={PARTNER_ID}&timestamp={timestamp}&sign={sign}&redirect={REDIRECT_URL}"
    print(f"[LOGIN URL] Redirecting to: {url}")
    return redirect(url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    shop_id = request.args.get('shop_id')
    timestamp = int(time.time())
    path = '/auth/token/get'
    sign = gen_signature('/api/v2' + path, timestamp)

    payload = {
        'code': code,
        'shop_id': int(shop_id),
        'partner_id': PARTNER_ID,
        'sign': sign,
        'timestamp': timestamp
    }

    try:
        print(f"[Shopee CALLBACK] Payload: {payload}")
        response = requests.post(API_BASE_URL + path, json=payload)
        print(f"[Shopee CALLBACK] Status Code: {response.status_code}")
        res = response.json()
        print(f"[Shopee CALLBACK] Response JSON: {res}")
    except Exception as e:
        print(f"[Shopee CALLBACK ERROR] Exception saat request: {e}")
        return "Error saat memanggil Shopee API"

    if 'access_token' not in res:
        print(f"[Shopee CALLBACK ERROR] access_token tidak ditemukan: {res}")
        return "Gagal ambil token dari Shopee: " + str(res)

    session['access_token'] = res['access_token']
    session['shop_id'] = shop_id
    print(f"[Shopee CALLBACK] Berhasil login. Token: {res['access_token']}")
    return redirect('/')

@app.route('/get_sales', methods=['POST'])
def get_sales():
    access_token = session.get('access_token')
    shop_id = session.get('shop_id')
    if not access_token:
        return redirect('/')

    date_from = request.form['date_from']
    date_to = request.form['date_to']

    time_from = int(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
    time_to = int(time.mktime(time.strptime(date_to, "%Y-%m-%d")))

    timestamp = int(time.time())
    path = '/order/get_order_list'
    sign = gen_signature('/api/v2' + path, timestamp)

    payload = {
        "partner_id": PARTNER_ID,
        "access_token": access_token,
        "shop_id": int(shop_id),
        "timestamp": timestamp,
        "sign": sign,
        "time_range_field": "create_time",
        "time_from": time_from,
        "time_to": time_to,
        "page_size": 100
    }

    res = requests.post(API_BASE_URL + path, json=payload).json()
    order_sn_list = res.get('response', {}).get('order_sn_list', [])

    data = []
    for order_sn in order_sn_list:
        detail_res = shopee_post('/order/get_order_detail', {
            'access_token': access_token,
            'shop_id': int(shop_id),
            'order_sn': order_sn
        })
        data.append(detail_res.get('response', {}))

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="sales_report.xlsx", as_attachment=True)

# ========== JALANKAN ==========
if __name__ == '__main__':
    app.run(debug=True)