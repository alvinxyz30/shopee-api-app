import hashlib
import hmac
import time
import urllib.parse
import requests
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from models import Shop, APILog, db

class ShopeeAPIError(Exception):
    """Custom exception untuk Shopee API errors"""
    pass

class ShopeeAPI:
    """Class untuk handle semua komunikasi dengan Shopee API"""
    
    def __init__(self, partner_id: str, partner_key: str, base_url: str):
        self.partner_id = partner_id
        self.partner_key = partner_key
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
        
        # Validasi parameter wajib
        if not all([partner_id, partner_key, base_url]):
            raise ValueError("Partner ID, Partner Key, dan Base URL harus diisi")
    
    def _generate_signature(self, path: str, timestamp: int, access_token: str = "", shop_id: str = "") -> str:
        """
        Generate signature untuk Shopee API
        Format: HMAC-SHA256(partner_id + path + timestamp + access_token + shop_id, partner_key)
        """
        try:
            # Gabungkan semua parameter sesuai urutan Shopee
            base_string = f"{self.partner_id}{path}{timestamp}"
            
            if access_token:
                base_string += access_token
            if shop_id:
                base_string += shop_id
            
            # Generate HMAC-SHA256 signature
            signature = hmac.new(
                self.partner_key.encode('utf-8'),
                base_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            self.logger.error(f"Error generating signature: {str(e)}")
            raise ShopeeAPIError(f"Gagal generate signature: {str(e)}")
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, 
                     access_token: str = "", shop_id: str = "") -> Dict[str, Any]:
        """
        Buat request ke Shopee API dengan proper authentication
        """
        try:
            timestamp = int(time.time())
            path = f"/api/v2{endpoint}"
            signature = self._generate_signature(path, timestamp, access_token, shop_id)
            
            # Base parameters untuk semua request
            base_params = {
                'partner_id': self.partner_id,
                'timestamp': timestamp,
                'sign': signature
            }
            
            # Tambahkan access_token dan shop_id jika tersedia
            if access_token:
                base_params['access_token'] = access_token
            if shop_id:
                base_params['shop_id'] = shop_id
            
            # Gabungkan dengan parameter request
            if params:
                base_params.update(params)
            
            url = f"{self.base_url}{path}"
            
            # Log request
            self.logger.info(f"Making {method} request to {endpoint}")
            start_time = time.time()
            
            # Buat request
            if method.upper() == 'GET':
                response = requests.get(url, params=base_params, timeout=30)
            else:
                response = requests.post(url, json=base_params, timeout=30)
            
            response_time = time.time() - start_time
            
            # Log ke database jika shop_id tersedia
            if shop_id:
                self._log_api_call(shop_id, endpoint, method, response.status_code, 
                                 response_time, None, json.dumps(params) if params else None)
            
            # Validasi response
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                if shop_id:
                    self._log_api_call(shop_id, endpoint, method, response.status_code, 
                                     response_time, error_msg, json.dumps(params) if params else None)
                raise ShopeeAPIError(error_msg)
            
            response_data = response.json()
            
            # Cek error dari API Shopee
            if 'error' in response_data:
                error_msg = f"Shopee API Error: {response_data.get('message', 'Unknown error')}"
                self.logger.error(error_msg)
                if shop_id:
                    self._log_api_call(shop_id, endpoint, method, response.status_code, 
                                     response_time, error_msg, json.dumps(params) if params else None)
                raise ShopeeAPIError(error_msg)
            
            return response_data
            
        except requests.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            self.logger.error(error_msg)
            if shop_id:
                self._log_api_call(shop_id, endpoint, method, 0, 0, error_msg, 
                                 json.dumps(params) if params else None)
            raise ShopeeAPIError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            raise ShopeeAPIError(error_msg)
    
    def _log_api_call(self, shop_id: str, endpoint: str, method: str, status_code: int, 
                     response_time: float, error_message: str = None, request_params: str = None):
        """Log API call ke database"""
        try:
            log = APILog(
                shop_id=shop_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                error_message=error_message,
                request_params=request_params
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log API call: {str(e)}")
    
    def generate_auth_url(self, redirect_url: str) -> str:
        """
        Generate URL untuk OAuth authorization
        """
        try:
            timestamp = int(time.time())
            path = "/api/v2/shop/auth_partner"
            signature = self._generate_signature(path, timestamp)
            
            params = {
                'partner_id': self.partner_id,
                'timestamp': timestamp,
                'sign': signature,
                'redirect': redirect_url
            }
            
            query_string = urllib.parse.urlencode(params)
            auth_url = f"{self.base_url}/api/v2/shop/auth_partner?{query_string}"
            
            self.logger.info(f"Generated auth URL: {auth_url}")
            return auth_url
            
        except Exception as e:
            self.logger.error(f"Error generating auth URL: {str(e)}")
            raise ShopeeAPIError(f"Gagal generate auth URL: {str(e)}")
    
    def get_access_token(self, code: str, shop_id: str) -> Dict[str, Any]:
        """
        Tukar authorization code dengan access token
        """
        try:
            params = {
                'code': code,
                'shop_id': shop_id,
                'partner_id': self.partner_id
            }
            
            response = self._make_request('POST', '/auth/token/get', params)
            
            # Validasi response
            if 'access_token' not in response or 'refresh_token' not in response:
                raise ShopeeAPIError("Invalid token response from Shopee API")
            
            self.logger.info(f"Successfully obtained access token for shop {shop_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting access token: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan access token: {str(e)}")
    
    def refresh_access_token(self, refresh_token: str, shop_id: str) -> Dict[str, Any]:
        """
        Refresh access token menggunakan refresh token
        """
        try:
            params = {
                'refresh_token': refresh_token,
                'shop_id': shop_id,
                'partner_id': self.partner_id
            }
            
            response = self._make_request('POST', '/auth/access_token/get', params)
            
            if 'access_token' not in response:
                raise ShopeeAPIError("Invalid refresh token response from Shopee API")
            
            self.logger.info(f"Successfully refreshed access token for shop {shop_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error refreshing access token: {str(e)}")
            raise ShopeeAPIError(f"Gagal refresh access token: {str(e)}")
    
    def get_shop_info(self, access_token: str, shop_id: str) -> Dict[str, Any]:
        """
        Ambil informasi toko
        """
        try:
            response = self._make_request('GET', '/shop/get_shop_info', {}, access_token, shop_id)
            return response
        except Exception as e:
            self.logger.error(f"Error getting shop info: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan info toko: {str(e)}")
    
    def get_order_list(self, access_token: str, shop_id: str, time_from: int, time_to: int, 
                      page_size: int = 100, cursor: str = "") -> Dict[str, Any]:
        """
        Ambil daftar order
        """
        try:
            params = {
                'time_range_field': 'create_time',
                'time_from': time_from,
                'time_to': time_to,
                'page_size': page_size
            }
            
            if cursor:
                params['cursor'] = cursor
            
            response = self._make_request('GET', '/order/get_order_list', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting order list: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan daftar order: {str(e)}")
    
    def get_order_detail(self, access_token: str, shop_id: str, order_sn_list: List[str]) -> Dict[str, Any]:
        """
        Ambil detail order
        """
        try:
            # Validasi maksimal 50 order per request
            if len(order_sn_list) > 50:
                raise ValueError("Maksimal 50 order per request")
            
            params = {
                'order_sn_list': order_sn_list,
                'response_optional_fields': [
                    'buyer_user_id', 'buyer_username', 'estimated_shipping_fee',
                    'recipient_address', 'actual_shipping_fee', 'goods_to_declare',
                    'note', 'note_update_time', 'item_list', 'pay_time',
                    'dropshipper', 'dropshipper_phone', 'split_up',
                    'buyer_cancel_reason', 'cancel_by', 'cancel_reason',
                    'actual_shipping_fee_confirmed', 'buyer_cpf_id',
                    'fulfillment_flag', 'pickup_done_time', 'package_list',
                    'shipping_carrier', 'payment_method', 'total_amount',
                    'buyer_username', 'invoice_data', 'checkout_shipping_carrier'
                ]
            }
            
            response = self._make_request('POST', '/order/get_order_detail', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting order detail: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan detail order: {str(e)}")
    
    def get_item_list(self, access_token: str, shop_id: str, offset: int = 0, page_size: int = 100, 
                     item_status: str = "") -> Dict[str, Any]:
        """
        Ambil daftar produk
        """
        try:
            params = {
                'offset': offset,
                'page_size': page_size
            }
            
            # Item status: NORMAL, DELETED, BANNED, UNLIST
            if item_status:
                params['item_status'] = item_status
            
            response = self._make_request('GET', '/product/get_item_list', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting item list: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan daftar produk: {str(e)}")
    
    def get_item_base_info(self, access_token: str, shop_id: str, item_id_list: List[int]) -> Dict[str, Any]:
        """
        Ambil informasi dasar produk
        """
        try:
            # Validasi maksimal 50 item per request
            if len(item_id_list) > 50:
                raise ValueError("Maksimal 50 item per request")
            
            params = {
                'item_id_list': item_id_list,
                'need_tax_info': True,
                'need_complaint_policy': True
            }
            
            response = self._make_request('GET', '/product/get_item_base_info', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting item base info: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan info produk: {str(e)}")
    
    def get_return_list(self, access_token: str, shop_id: str, page_no: int = 1, page_size: int = 20,
                       create_time_from: int = None, create_time_to: int = None) -> Dict[str, Any]:
        """
        Ambil daftar return/refund
        """
        try:
            params = {
                'page_no': page_no,
                'page_size': page_size
            }
            
            if create_time_from:
                params['create_time_from'] = create_time_from
            if create_time_to:
                params['create_time_to'] = create_time_to
            
            response = self._make_request('GET', '/returns/get_return_list', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting return list: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan daftar return: {str(e)}")
    
    def get_return_detail(self, access_token: str, shop_id: str, return_sn_list: List[str]) -> Dict[str, Any]:
        """
        Ambil detail return/refund
        """
        try:
            # Validasi maksimal 50 return per request
            if len(return_sn_list) > 50:
                raise ValueError("Maksimal 50 return per request")
            
            params = {
                'return_sn_list': return_sn_list
            }
            
            response = self._make_request('GET', '/returns/get_return_detail', params, access_token, shop_id)
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting return detail: {str(e)}")
            raise ShopeeAPIError(f"Gagal mendapatkan detail return: {str(e)}")