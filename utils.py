import pandas as pd
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from models import Shop, DataExport, db

logger = logging.getLogger(__name__)

def validate_date_range(date_from: str, date_to: str, max_days: int = 365) -> tuple:
    """
    Validasi dan konversi range tanggal
    """
    try:
        # Parse tanggal
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d')
        
        # Validasi range
        if start_date > end_date:
            raise ValueError("Tanggal mulai tidak boleh lebih besar dari tanggal akhir")
        
        # Validasi maksimal range
        if (end_date - start_date).days > max_days:
            raise ValueError(f"Range tanggal maksimal {max_days} hari")
        
        # Validasi tidak boleh tanggal masa depan
        if end_date > datetime.now():
            end_date = datetime.now()
        
        return start_date, end_date
        
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError("Format tanggal harus YYYY-MM-DD")
        raise e

def convert_timestamp_to_datetime(timestamp: int) -> str:
    """
    Konversi timestamp ke format datetime string
    """
    try:
        if not timestamp:
            return ""
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ""

def get_order_status_text(status: str) -> str:
    """
    Konversi status order ke teks yang mudah dibaca
    """
    status_mapping = {
        'UNPAID': 'Belum Dibayar',
        'TO_CONFIRM_RECEIVE': 'Menunggu Konfirmasi Penerimaan',
        'TO_SHIP': 'Siap Dikirim',
        'READY_TO_SHIP': 'Siap Dikirim',
        'RETRY_SHIP': 'Coba Kirim Ulang',
        'SHIPPED': 'Dalam Pengiriman',
        'DELIVERED': 'Terkirim',
        'COMPLETED': 'Selesai',
        'IN_CANCEL': 'Dalam Pembatalan',
        'CANCELLED': 'Dibatalkan',
        'TO_RETURN': 'Akan Dikembalikan',
        'PROCESSING': 'Diproses'
    }
    return status_mapping.get(status, status)

def get_payment_method_text(method: str) -> str:
    """
    Konversi payment method ke teks yang mudah dibaca
    """
    payment_mapping = {
        'COD': 'COD (Bayar di Tempat)',
        'CREDIT_CARD': 'Kartu Kredit',
        'BANK_TRANSFER': 'Transfer Bank',
        'INSTALLMENT': 'Cicilan',
        'WALLET': 'E-Wallet',
        'SHOPEE_PAY': 'ShopeePay'
    }
    return payment_mapping.get(method, method)

def format_currency(amount: float, currency: str = 'IDR') -> str:
    """
    Format currency dengan proper formatting
    """
    if not amount:
        return f"0 {currency}"
    
    if currency == 'IDR':
        return f"Rp {amount:,.0f}".replace(',', '.')
    else:
        return f"{amount:,.2f} {currency}"

def flatten_order_data(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten data order untuk export ke Excel
    """
    flattened = {}
    
    # Basic order info
    flattened['order_sn'] = order_data.get('order_sn', '')
    flattened['order_status'] = get_order_status_text(order_data.get('order_status', ''))
    flattened['create_time'] = convert_timestamp_to_datetime(order_data.get('create_time'))
    flattened['update_time'] = convert_timestamp_to_datetime(order_data.get('update_time'))
    flattened['pay_time'] = convert_timestamp_to_datetime(order_data.get('pay_time'))
    
    # Financial info
    flattened['total_amount'] = order_data.get('total_amount', 0)
    flattened['actual_shipping_fee'] = order_data.get('actual_shipping_fee', 0)
    flattened['goods_to_declare'] = order_data.get('goods_to_declare', False)
    flattened['currency'] = order_data.get('currency', 'IDR')
    
    # Payment info
    flattened['payment_method'] = get_payment_method_text(order_data.get('payment_method', ''))
    
    # Buyer info
    flattened['buyer_username'] = order_data.get('buyer_username', '')
    flattened['buyer_user_id'] = order_data.get('buyer_user_id', '')
    
    # Shipping info
    recipient = order_data.get('recipient_address', {})
    flattened['recipient_name'] = recipient.get('name', '')
    flattened['recipient_phone'] = recipient.get('phone', '')
    flattened['recipient_address'] = f"{recipient.get('full_address', '')} {recipient.get('city', '')} {recipient.get('state', '')}"
    
    flattened['shipping_carrier'] = order_data.get('shipping_carrier', '')
    flattened['tracking_no'] = order_data.get('tracking_no', '')
    
    # Order notes
    flattened['note'] = order_data.get('note', '')
    flattened['message_to_seller'] = order_data.get('message_to_seller', '')
    
    # Cancel info
    flattened['cancel_reason'] = order_data.get('cancel_reason', '')
    flattened['cancel_by'] = order_data.get('cancel_by', '')
    
    # Items info (simplified)
    item_list = order_data.get('item_list', [])
    if item_list:
        first_item = item_list[0]
        flattened['item_name'] = first_item.get('item_name', '')
        flattened['item_sku'] = first_item.get('item_sku', '')
        flattened['model_name'] = first_item.get('model_name', '')
        flattened['quantity'] = sum(item.get('model_quantity', 0) for item in item_list)
        flattened['total_items'] = len(item_list)
    else:
        flattened['item_name'] = ''
        flattened['item_sku'] = ''
        flattened['model_name'] = ''
        flattened['quantity'] = 0
        flattened['total_items'] = 0
    
    return flattened

def flatten_product_data(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten data produk untuk export ke Excel
    """
    flattened = {}
    
    # Basic product info
    flattened['item_id'] = product_data.get('item_id', '')
    flattened['item_name'] = product_data.get('item_name', '')
    flattened['item_sku'] = product_data.get('item_sku', '')
    flattened['create_time'] = convert_timestamp_to_datetime(product_data.get('create_time'))
    flattened['update_time'] = convert_timestamp_to_datetime(product_data.get('update_time'))
    
    # Status and availability
    flattened['item_status'] = product_data.get('item_status', '')
    flattened['has_model'] = product_data.get('has_model', False)
    
    # Category
    category_list = product_data.get('category_list', [])
    flattened['category'] = ' > '.join([cat.get('display_category_name', '') for cat in category_list])
    
    # Images
    image_list = product_data.get('image', {}).get('image_url_list', [])
    flattened['image_count'] = len(image_list)
    flattened['main_image'] = image_list[0] if image_list else ''
    
    # Description
    flattened['description'] = product_data.get('description', '')
    
    # Dimensions and weight
    flattened['weight'] = product_data.get('weight', 0)
    dimension = product_data.get('dimension', {})
    flattened['package_length'] = dimension.get('package_length', 0)
    flattened['package_width'] = dimension.get('package_width', 0)
    flattened['package_height'] = dimension.get('package_height', 0)
    
    # Pricing (dari model atau item)
    price_info = product_data.get('price_info', {})
    flattened['currency'] = price_info.get('currency', 'IDR')
    flattened['original_price'] = price_info.get('original_price', 0)
    flattened['current_price'] = price_info.get('current_price', 0)
    
    # Stock info
    stock_info = product_data.get('stock_info', {})
    flattened['normal_stock'] = stock_info.get('normal_stock', 0)
    flattened['reserved_stock'] = stock_info.get('reserved_stock', 0)
    
    # Sales info
    flattened['sales'] = product_data.get('sales', 0)
    flattened['views'] = product_data.get('views', 0)
    flattened['likes'] = product_data.get('likes', 0)
    
    # Brand
    brand = product_data.get('brand', {})
    flattened['brand_name'] = brand.get('display_brand_name', '')
    
    return flattened

def flatten_return_data(return_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten data return untuk export ke Excel
    """
    flattened = {}
    
    # Basic return info
    flattened['return_sn'] = return_data.get('return_sn', '')
    flattened['order_sn'] = return_data.get('order_sn', '')
    flattened['return_status'] = return_data.get('status', '')
    flattened['create_time'] = convert_timestamp_to_datetime(return_data.get('create_time'))
    flattened['update_time'] = convert_timestamp_to_datetime(return_data.get('update_time'))
    
    # Return reason
    flattened['reason'] = return_data.get('reason', '')
    flattened['text_reason'] = return_data.get('text_reason', '')
    flattened['dispute_reason'] = return_data.get('dispute_reason', '')
    
    # Amount info
    flattened['return_amount'] = return_data.get('return_amount', 0)
    flattened['currency'] = return_data.get('currency', 'IDR')
    
    # User info
    user = return_data.get('user', {})
    flattened['buyer_username'] = user.get('username', '')
    flattened['buyer_user_id'] = user.get('user_id', '')
    
    # Return shipping info
    return_shipping = return_data.get('return_shipping', {})
    flattened['return_tracking_number'] = return_shipping.get('tracking_number', '')
    flattened['return_shipping_carrier'] = return_shipping.get('shipping_carrier', '')
    
    # Item info
    item = return_data.get('item', {})
    flattened['item_name'] = item.get('item_name', '')
    flattened['item_sku'] = item.get('item_sku', '')
    flattened['model_name'] = item.get('model_name', '')
    flattened['model_sku'] = item.get('model_sku', '')
    flattened['return_quantity'] = item.get('amount', 0)
    
    # Due date
    flattened['due_date'] = convert_timestamp_to_datetime(return_data.get('due_date'))
    
    # Images (return proof)
    image_list = return_data.get('image', [])
    flattened['proof_image_count'] = len(image_list)
    
    return flattened

def export_to_excel(data: List[Dict], filename: str, sheet_name: str = 'Data') -> str:
    """
    Export data ke Excel file
    """
    try:
        if not data:
            raise ValueError("Tidak ada data untuk di-export")
        
        # Buat directory exports jika belum ada
        exports_dir = os.path.join(os.getcwd(), 'exports')
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)
        
        # Buat filepath lengkap
        filepath = os.path.join(exports_dir, filename)
        
        # Convert ke DataFrame
        df = pd.DataFrame(data)
        
        # Export ke Excel dengan formatting
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Get worksheet untuk formatting
            worksheet = writer.sheets[sheet_name]
            
            # Auto-adjust column width
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Max width 50
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"Data exported successfully to {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        raise e

def validate_shop_limit(shop_count: int, max_shops: int = 10) -> bool:
    """
    Validasi batas maksimal toko
    """
    return shop_count < max_shops

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename untuk keamanan
    """
    import re
    # Remove atau replace karakter yang tidak aman
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Batasi panjang filename
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:100-len(ext)] + ext
    return filename

def create_export_record(shop_id: str, export_type: str, date_from: datetime = None, 
                        date_to: datetime = None) -> DataExport:
    """
    Buat record export di database
    """
    try:
        export_record = DataExport(
            shop_id=shop_id,
            export_type=export_type,
            date_from=date_from,
            date_to=date_to,
            status='pending'
        )
        db.session.add(export_record)
        db.session.commit()
        return export_record
    except Exception as e:
        logger.error(f"Error creating export record: {str(e)}")
        db.session.rollback()
        raise e

def update_export_record(export_id: int, total_records: int, file_path: str = None, 
                        status: str = 'completed') -> None:
    """
    Update record export di database
    """
    try:
        export_record = DataExport.query.get(export_id)
        if export_record:
            export_record.total_records = total_records
            export_record.file_path = file_path
            export_record.status = status
            export_record.completed_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        logger.error(f"Error updating export record: {str(e)}")
        db.session.rollback()
        raise e