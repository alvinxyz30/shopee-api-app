# Quick Start Guide - Shopee API Integration

## Cara Cepat Menjalankan Aplikasi

### 1. Setup Environment
```bash
# Copy dan edit file environment
copy .env.example .env
# Edit .env dengan konfigurasi Anda
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
python run.py --init-db
```

### 4. Run Application
```bash
python run.py
```

Atau gunakan script otomatis:
- **Windows**: `start.bat`
- **Linux/Mac**: `./start.sh`

### 5. Access Application
Buka browser: `http://localhost:5000`

## Konfigurasi Minimum (.env)

```env
SHOPEE_PARTNER_ID=1175215
SHOPEE_PARTNER_KEY=shpk455a5a6364684f774d745463694e6669564878566a7a466a4b6558507648
SHOPEE_REDIRECT_URL=https://alvinnovendra2.pythonanywhere.com/auth_callback
SHOPEE_BASE_URL=https://partner.test-stable.shopeemobile.com
FLASK_SECRET_KEY=your-secret-key-here
```

## Test Data

```
Shop Account: SANDBOX.2cd0a6e7d69d9f56cf00
Shop Password: 9528728e1dd6c63d
Shop ID: 225535624
```

## Fitur Utama

✅ **Multi-shop support** (maksimal 10 toko)
✅ **OAuth authentication** dengan auto-refresh token
✅ **Data Orders** - View & export pesanan
✅ **Data Products** - View & export produk  
✅ **Data Returns** - View & export retur
✅ **Excel export** dengan filter tanggal
✅ **API logging** untuk monitoring
✅ **Error handling** yang comprehensive

## Flow Penggunaan

1. **Tambah Toko** → Klik "Tambah Toko Baru"
2. **Login OAuth** → Masukkan credentials dan authorize
3. **Pilih Data** → Orders, Products, atau Returns
4. **View & Export** → Lihat data dan export ke Excel

Aplikasi siap digunakan! 🚀