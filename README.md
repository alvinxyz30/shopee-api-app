# Shopee API Integration Application

Aplikasi web berbasis Python Flask untuk mengintegrasikan dan mengelola data dari Shopee Open Platform API v2. Aplikasi ini memungkinkan Anda untuk:

- Mengelola multiple toko Shopee (maksimal 10 toko)
- Otentikasi OAuth dengan token refresh otomatis
- Mengambil dan menampilkan data orders, products, dan returns
- Export data ke Excel dengan filter tanggal
- Monitoring API logs dan error handling

## Fitur Utama

### 🏪 Multi-Shop Management
- Support hingga 10 toko dalam satu aplikasi
- OAuth authentication flow yang aman
- Auto-refresh token setiap 3 jam
- Management token per toko

### 📊 Data Management
- **Data Orders**: View dan export data pesanan dengan detail lengkap
- **Data Products**: View dan export data produk, stok, dan harga
- **Data Returns**: View dan export data return/refund dengan alasan

### 📈 Export & Reporting
- Export ke Excel (.xlsx) format
- Filter berdasarkan range tanggal (hingga 2.5 tahun untuk returns)
- Pagination untuk performance optimal
- Auto-download file export

### 🔧 Monitoring & Logging
- API call logging untuk debugging
- Error handling dan retry mechanism
- Performance monitoring (response time)
- Token status monitoring

## Prerequisites

- Python 3.8+
- Shopee Open Platform Account
- Partner ID dan Partner Key dari Shopee
- Domain untuk redirect URL (bisa menggunakan ngrok untuk testing)

## Installation

### 1. Clone atau Download Project
```bash
# Download dan extract project ke folder shopee_api_app
```

### 2. Install Dependencies
```bash
cd shopee_api_app
pip install -r requirements.txt
```

### 3. Setup Environment Variables
Edit file `.env` dengan konfigurasi Anda:

```env
# Shopee API Configuration
SHOPEE_PARTNER_ID=your_partner_id
SHOPEE_PARTNER_KEY=your_partner_key
SHOPEE_REDIRECT_URL=https://yourdomain.com/auth_callback
SHOPEE_BASE_URL=https://partner.test-stable.shopeemobile.com

# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///shopee_app.db

# Optional: Test Shop Data
TEST_SHOP_ID=your_test_shop_id
TEST_SHOP_ACCOUNT=your_test_shop_account
TEST_SHOP_PASSWORD=your_test_shop_password
```

### 4. Initialize Database
```bash
python run.py --init-db
```

### 5. Run Application
```bash
python run.py
```

Aplikasi akan berjalan di `http://localhost:5000`

## Konfigurasi Shopee API

### 1. Dapatkan Partner ID dan Partner Key
1. Daftar di [Shopee Open Platform](https://open.shopee.com)
2. Buat aplikasi baru
3. Dapatkan Partner ID dan Partner Key
4. Setup redirect URL

### 2. Setup Redirect URL
Redirect URL harus dapat diakses dari internet. Untuk testing lokal, Anda bisa menggunakan:

- **ngrok**: `ngrok http 5000` kemudian gunakan URL yang diberikan
- **PythonAnywhere**: Deploy aplikasi ke PythonAnywhere
- **Heroku**: Deploy ke Heroku

### 3. Test Environment
Untuk testing, gunakan:
- Base URL: `https://partner.test-stable.shopeemobile.com`
- Test shop credentials yang disediakan Shopee

## Cara Penggunaan

### 1. Tambah Toko Pertama
1. Buka aplikasi di browser
2. Klik "Tambah Toko Baru"
3. Masukkan Shop Account dan Password
4. Klik "Mulai Autentikasi"
5. Login di halaman Shopee dengan credentials
6. Konfirmasi otorisasi
7. Toko akan otomatis ditambahkan

### 2. Akses Data
Setelah toko berhasil ditambahkan:
1. Klik nama toko di dashboard
2. Pilih jenis data yang ingin dilihat:
   - **Data Order**: Pesanan dan transaksi
   - **Data Produk**: Katalog produk dan stok
   - **Data Return**: Return dan refund

### 3. Export Data
1. Dari halaman detail toko, klik tombol export yang diinginkan
2. Untuk orders dan returns, Anda bisa set range tanggal
3. File Excel akan otomatis ter-download

### 4. Monitoring
1. Akses "Lihat Log API" untuk melihat aktivitas API
2. Monitor status token di dashboard
3. Token akan auto-refresh setiap 3 jam

## Struktur File

```
shopee_api_app/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── models.py           # Database models
├── shopee_api.py       # Shopee API integration
├── scheduler.py        # Token refresh scheduler
├── utils.py            # Utility functions
├── run.py              # Application entry point
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── README.md           # Documentation
└── templates/          # HTML templates
    ├── base.html
    ├── index.html
    ├── add_shop.html
    ├── shop_detail.html
    ├── orders.html
    ├── products.html
    ├── returns.html
    └── api_logs.html
```

## API Endpoints

### Internal API Routes
- `GET /` - Dashboard
- `GET /add_shop` - Form tambah toko
- `POST /auth_shop` - Proses autentikasi
- `GET /auth_callback` - OAuth callback
- `GET /shop/<shop_id>` - Detail toko
- `GET /shop/<shop_id>/orders` - Data orders
- `GET /shop/<shop_id>/products` - Data products
- `GET /shop/<shop_id>/returns` - Data returns
- `GET /export/<shop_id>/<data_type>` - Export data
- `POST /delete_shop/<shop_id>` - Hapus toko
- `GET /api_logs/<shop_id>` - API logs

### Shopee API Endpoints Used
- `/api/v2/shop/auth_partner` - OAuth authorization
- `/api/v2/auth/token/get` - Get access token
- `/api/v2/auth/access_token/get` - Refresh access token
- `/api/v2/shop/get_shop_info` - Shop information
- `/api/v2/order/get_order_list` - Order list
- `/api/v2/order/get_order_detail` - Order details
- `/api/v2/product/get_item_list` - Product list
- `/api/v2/product/get_item_base_info` - Product details
- `/api/v2/returns/get_return_list` - Return list
- `/api/v2/returns/get_return_detail` - Return details

## Troubleshooting

### Token Issues
```
Error: Token expired
```
**Solusi**: Token akan auto-refresh setiap 3 jam. Jika masih error, login ulang toko.

### API Rate Limiting
```
Error: Too many requests
```
**Solusi**: Shopee API memiliki rate limit. Tunggu beberapa menit sebelum mencoba lagi.

### Invalid Signature
```
Error: Invalid signature
```
**Solusi**: Pastikan Partner Key dan timestamp correct. Cek system time.

### Database Issues
```
Error: Database locked
```
**Solusi**: Restart aplikasi atau jalankan `python run.py --init-db`

### Export Timeout
```
Error: Export timeout
```
**Solusi**: Kurangi range tanggal atau gunakan pagination.

## Development

### Add New Features
1. Tambah route di `app.py`
2. Tambah model di `models.py` jika perlu
3. Tambah template HTML di `templates/`
4. Update `utils.py` untuk helper functions

### Testing
```bash
# Test dengan data sandbox
python run.py
```

### Production Deployment
1. Set `FLASK_DEBUG=False`
2. Use production database (PostgreSQL)
3. Configure proper logging
4. Use WSGI server (Gunicorn, uWSGI)
5. Setup reverse proxy (Nginx)

## Security Notes

- Jangan commit `.env` file ke repository
- Gunakan HTTPS untuk production
- Regularly rotate API keys
- Monitor API logs untuk suspicious activity
- Set proper file permissions

## Support

Untuk pertanyaan atau issues:
1. Check troubleshooting section
2. Check Shopee Open Platform documentation
3. Review API logs untuk error details

## License

This project is for educational and internal business use only. 
Ensure compliance with Shopee Open Platform terms of service.

---

**Developed with ❤️ for Shopee API Integration**