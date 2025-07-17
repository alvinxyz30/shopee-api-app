import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from models import Shop, db
from shopee_api import ShopeeAPI, ShopeeAPIError

logger = logging.getLogger(__name__)

class TokenRefreshScheduler:
    """Scheduler untuk refresh token otomatis"""
    
    def __init__(self, shopee_api: ShopeeAPI):
        self.shopee_api = shopee_api
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func=self.refresh_tokens,
            trigger=IntervalTrigger(hours=3),  # Cek setiap 3 jam
            id='token_refresh',
            name='Refresh Shopee Access Tokens',
            replace_existing=True
        )
        logger.info("Token refresh scheduler initialized")
    
    def start(self):
        """Start scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Token refresh scheduler started")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
    
    def stop(self):
        """Stop scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Token refresh scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    def refresh_tokens(self):
        """
        Cek dan refresh token yang akan expired
        """
        try:
            logger.info("Starting token refresh check...")
            
            # Cari semua toko aktif dengan token yang akan expired
            shops_to_refresh = Shop.query.filter(
                Shop.is_active == True,
                Shop.refresh_token.isnot(None),
                Shop.expires_at <= datetime.utcnow() + timedelta(minutes=30)
            ).all()
            
            if not shops_to_refresh:
                logger.info("No tokens need refreshing")
                return
            
            logger.info(f"Found {len(shops_to_refresh)} shops with tokens to refresh")
            
            success_count = 0
            error_count = 0
            
            for shop in shops_to_refresh:
                try:
                    logger.info(f"Refreshing token for shop {shop.shop_id}")
                    
                    # Refresh token
                    token_response = self.shopee_api.refresh_access_token(
                        shop.refresh_token, shop.shop_id
                    )
                    
                    new_access_token = token_response.get('access_token')
                    new_refresh_token = token_response.get('refresh_token', shop.refresh_token)
                    expires_in = token_response.get('expires_in', 14400)
                    
                    if new_access_token:
                        # Update token di database
                        shop.update_tokens(new_access_token, new_refresh_token, expires_in)
                        success_count += 1
                        logger.info(f"Successfully refreshed token for shop {shop.shop_id}")
                    else:
                        logger.error(f"No access token in refresh response for shop {shop.shop_id}")
                        error_count += 1
                        
                except ShopeeAPIError as e:
                    logger.error(f"Shopee API error refreshing token for shop {shop.shop_id}: {str(e)}")
                    
                    # Jika refresh token invalid, tandai toko sebagai perlu re-auth
                    if "invalid" in str(e).lower() or "expired" in str(e).lower():
                        shop.access_token = None
                        shop.refresh_token = None
                        shop.expires_at = None
                        db.session.commit()
                        logger.warning(f"Marked shop {shop.shop_id} for re-authentication")
                    
                    error_count += 1
                    
                except Exception as e:
                    logger.error(f"Unexpected error refreshing token for shop {shop.shop_id}: {str(e)}")
                    error_count += 1
            
            logger.info(f"Token refresh completed: {success_count} success, {error_count} errors")
            
        except Exception as e:
            logger.error(f"Error in token refresh job: {str(e)}")
    
    def refresh_shop_token(self, shop_id: str) -> bool:
        """
        Refresh token untuk toko tertentu (manual trigger)
        """
        try:
            shop = Shop.query.filter_by(shop_id=shop_id, is_active=True).first()
            if not shop:
                logger.error(f"Shop {shop_id} not found")
                return False
            
            if not shop.refresh_token:
                logger.error(f"No refresh token for shop {shop_id}")
                return False
            
            logger.info(f"Manually refreshing token for shop {shop_id}")
            
            # Refresh token
            token_response = self.shopee_api.refresh_access_token(
                shop.refresh_token, shop_id
            )
            
            new_access_token = token_response.get('access_token')
            new_refresh_token = token_response.get('refresh_token', shop.refresh_token)
            expires_in = token_response.get('expires_in', 14400)
            
            if new_access_token:
                # Update token di database
                shop.update_tokens(new_access_token, new_refresh_token, expires_in)
                logger.info(f"Successfully refreshed token for shop {shop_id}")
                return True
            else:
                logger.error(f"No access token in refresh response for shop {shop_id}")
                return False
                
        except ShopeeAPIError as e:
            logger.error(f"Shopee API error refreshing token for shop {shop_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error refreshing token for shop {shop_id}: {str(e)}")
            return False
    
    def get_scheduler_status(self) -> dict:
        """
        Get status scheduler dan informasi jobs
        """
        try:
            status = {
                'running': self.scheduler.running,
                'jobs': []
            }
            
            if self.scheduler.running:
                for job in self.scheduler.get_jobs():
                    job_info = {
                        'id': job.id,
                        'name': job.name,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                        'trigger': str(job.trigger)
                    }
                    status['jobs'].append(job_info)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting scheduler status: {str(e)}")
            return {'running': False, 'jobs': [], 'error': str(e)}
    
    def get_token_status_summary(self) -> dict:
        """
        Get summary status token semua toko
        """
        try:
            shops = Shop.query.filter_by(is_active=True).all()
            
            summary = {
                'total_shops': len(shops),
                'valid_tokens': 0,
                'expires_soon': 0,
                'expired_tokens': 0,
                'no_tokens': 0
            }
            
            for shop in shops:
                if not shop.access_token or not shop.expires_at:
                    summary['no_tokens'] += 1
                elif not shop.is_token_valid:
                    summary['expired_tokens'] += 1
                elif shop.token_expires_soon:
                    summary['expires_soon'] += 1
                else:
                    summary['valid_tokens'] += 1
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting token status summary: {str(e)}")
            return {'error': str(e)}