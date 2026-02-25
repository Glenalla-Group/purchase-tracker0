"""
Keepa API Service for fetching Amazon product prices
"""

import logging
import requests
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class KeepaService:
    """Service for interacting with Keepa API"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.keepa_api_key
        self.base_url = "https://api.keepa.com"
    
    def get_product_price(self, asin: str) -> Optional[float]:
        """
        Fetch current Amazon Buy Box price for an ASIN and apply 15% markup
        
        Args:
            asin: Amazon ASIN
            
        Returns:
            Price with 15% markup, or None if not available
        """
        try:
            # Create the API URL for product request
            url = f"{self.base_url}/product"
            params = {
                "key": self.api_key,
                "domain": 1,  # Amazon.com
                "asin": asin,
                "stats": 90,
                "update": 1
            }
            
            logger.info(f"Calling Keepa API for ASIN: {asin}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if we got data back
            if data.get("products") and len(data["products"]) > 0:
                product = data["products"][0]
                
                # Method 1: Get current price from stats object
                if product.get("stats") and product["stats"].get("current"):
                    current_stats = product["stats"]["current"]
                    
                    # Try the NEW price first (index 1 in the current stats array)
                    if len(current_stats) > 1 and current_stats[1] and current_stats[1] > 0:
                        price = current_stats[1] / 100  # Convert from Keepa's cents to dollars
                        logger.info(f"Found NEW price for {asin}: ${price}")
                        return round(price * 1.15, 2)  # Apply 15% markup
                    
                    # If NEW isn't available, try the Amazon price (index 0)
                    if len(current_stats) > 0 and current_stats[0] and current_stats[0] > 0:
                        price = current_stats[0] / 100
                        logger.info(f"Found Amazon price for {asin}: ${price}")
                        return round(price * 1.15, 2)  # Apply 15% markup
                    
                    # Try the Buy Box price (index 18)
                    if len(current_stats) > 18 and current_stats[18] and current_stats[18] > 0:
                        price = current_stats[18] / 100
                        logger.info(f"Found Buy Box price for {asin}: ${price}")
                        return round(price * 1.15, 2)  # Apply 15% markup
                
                # Method 2: Fallback - Look in data.NEW
                if product.get("data") and product["data"].get("NEW"):
                    new_prices = product["data"]["NEW"]
                    # Find the most recent price (last non-zero value)
                    for i in range(len(new_prices) - 1, -1, -1):
                        if new_prices[i] > 0:
                            price = new_prices[i] / 100
                            logger.info(f"Found price in data.NEW for {asin}: ${price}")
                            return round(price * 1.15, 2)  # Apply 15% markup
                
                # Method 3: Fallback - Look in csv.NEW
                if product.get("csv") and product["csv"].get("NEW"):
                    new_price_data = product["csv"]["NEW"]
                    for i in range(len(new_price_data) - 1, -1, -1):
                        if new_price_data[i] > 0:
                            price = new_price_data[i] / 100
                            logger.info(f"Found price in csv.NEW for {asin}: ${price}")
                            return round(price * 1.15, 2)  # Apply 15% markup
                
                logger.warning(f"No price found in any field for ASIN: {asin}")
                return None
            else:
                logger.warning(f"No product data returned for ASIN: {asin}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error fetching price from Keepa for ASIN {asin}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching price for ASIN {asin}: {e}")
            return None

