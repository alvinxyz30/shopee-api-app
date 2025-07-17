from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Shop(db.Model):
    """Model untuk menyimpan data toko"""
    __tablename__ = 'shops'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    shop_name = db.Column(db.String(100), nullable=True)
    shop_account = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<Shop {self.shop_id}: {self.shop_name}>'
    
    @property
    def is_token_valid(self):
        """Cek apakah token masih valid"""
        if not self.expires_at or not self.access_token:
            return False
        return datetime.utcnow() < self.expires_at
    
    @property
    def token_expires_soon(self):
        """Cek apakah token akan expired dalam 30 menit"""
        if not self.expires_at:
            return True
        return datetime.utcnow() + timedelta(minutes=30) >= self.expires_at
    
    def update_tokens(self, access_token, refresh_token, expires_in=14400):
        """Update token dengan validasi"""
        if not access_token or not refresh_token:
            raise ValueError("Access token dan refresh token tidak boleh kosong")
        
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.updated_at = datetime.utcnow()
        db.session.commit()

class APILog(db.Model):
    """Model untuk logging API calls"""
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.String(20), db.ForeignKey('shops.shop_id'), nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    response_time = db.Column(db.Float, nullable=True)  # dalam detik
    error_message = db.Column(db.Text, nullable=True)
    request_params = db.Column(db.Text, nullable=True)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    shop = db.relationship('Shop', backref=db.backref('api_logs', lazy=True))
    
    def __repr__(self):
        return f'<APILog {self.endpoint}: {self.status_code}>'

class DataExport(db.Model):
    """Model untuk tracking export data"""
    __tablename__ = 'data_exports'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.String(20), db.ForeignKey('shops.shop_id'), nullable=False)
    export_type = db.Column(db.String(50), nullable=False)  # orders, products, returns
    date_from = db.Column(db.DateTime, nullable=True)
    date_to = db.Column(db.DateTime, nullable=True)
    total_records = db.Column(db.Integer, nullable=False, default=0)
    file_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    shop = db.relationship('Shop', backref=db.backref('exports', lazy=True))
    
    def __repr__(self):
        return f'<DataExport {self.export_type}: {self.status}>'