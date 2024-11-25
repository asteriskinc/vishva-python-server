# amazon_search.py

import bottlenose
from typing import Dict, List, Optional
import xmltodict
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
import requests
from dataclasses import asdict
from .commerce_tools import ProductInfo

class AmazonProductAPI:
    def __init__(self):
        # Load credentials from environment variables
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.partner_tag = os.getenv('AWS_PARTNER_TAG')
        self.region = os.getenv('AWS_REGION', 'us-west-2')
        self.marketplace = os.getenv('AWS_MARKETPLACE', 'www.amazon.com')
        
        # API endpoint
        self.endpoint = f'webservices.{self.marketplace}'
        
        # Initialize bottlenose with error handling
        self.amazon = bottlenose.Amazon(
            self.access_key,
            self.secret_key,
            self.partner_tag,
            Region=self.region,
            MaxQPS=1,  # Queries per second
            ErrorHandler=self._error_handler
        )

    def _error_handler(self, err):
        """Handle API errors with exponential backoff"""
        ex = err['exception']
        if isinstance(ex, Exception):
            # Implement exponential backoff
            if hasattr(ex, 'status') and ex.status == 503:
                time.sleep(2.5)  # Wait for 2.5 seconds before retrying
                return True  # True = retry request
        return False

    def _parse_response(self, response: str) -> List[Dict]:
        """Parse XML response from Amazon API"""
        try:
            # Convert XML to dict
            response_dict = xmltodict.parse(response)
            
            # Extract items from response
            items = response_dict.get('ItemSearchResponse', {}).get('Items', {}).get('Item', [])
            if not isinstance(items, list):
                items = [items]
            
            return items
        except Exception as e:
            print(f"Error parsing Amazon response: {str(e)}")
            return []

    def _extract_product_info(self, item: Dict) -> ProductInfo:
        """Convert Amazon item data to ProductInfo object"""
        try:
            # Extract basic information
            item_attributes = item.get('ItemAttributes', {})
            offer_listing = item.get('Offers', {}).get('Offer', {}).get('OfferListing', {})
            
            # Extract price
            price_str = offer_listing.get('Price', {}).get('Amount', '0')
            price = float(price_str) / 100 if price_str.isdigit() else 0.0
            
            # Create ProductInfo object
            return ProductInfo(
                title=item_attributes.get('Title', ''),
                price=price,
                currency=offer_listing.get('Price', {}).get('CurrencyCode', 'USD'),
                seller='Amazon',
                url=item.get('DetailPageURL', ''),
                rating=float(item.get('CustomerReviews', {}).get('AverageRating', 0)),
                review_count=int(item.get('CustomerReviews', {}).get('TotalReviews', 0)),
                availability=offer_listing.get('Availability', ''),
                image_url=item.get('LargeImage', {}).get('URL', ''),
                description=item_attributes.get('Feature', []),
                specifications={
                    'brand': item_attributes.get('Brand', ''),
                    'model': item_attributes.get('Model', ''),
                    'color': item_attributes.get('Color', ''),
                    'size': item_attributes.get('Size', ''),
                    'weight': item_attributes.get('ItemDimensions', {}).get('Weight', '')
                },
                shipping_info={
                    'is_prime': offer_listing.get('IsEligibleForPrime', 'false') == 'true',
                    'is_free_shipping': offer_listing.get('IsEligibleForFreeShipping', 'false') == 'true',
                    'shipping_charge': offer_listing.get('Shipping', {}).get('Amount', 0)
                }
            )
        except Exception as e:
            print(f"Error extracting product info: {str(e)}")
            return None

    def search_products(
        self, 
        query: str, 
        filters: Optional[Dict] = None
    ) -> List[ProductInfo]:
        """
        Search for products on Amazon
        
        Args:
            query (str): Search query
            filters (Dict, optional): Additional search filters
                Supported filters:
                - category: str (e.g., 'Electronics', 'Books')
                - min_price: float
                - max_price: float
                - sort: str ('price-asc', 'price-desc', 'rating-desc')
                - condition: str ('New', 'Used', 'Refurbished')
                - prime_eligible: bool
                - free_shipping: bool
                - brand: str
                - min_rating: float (1-5)
        
        Returns:
            List[ProductInfo]: List of standardized product information
        """
        try:
            # Apply filters
            search_params = {
                'Keywords': query,
                'ResponseGroup': 'Large',
            }
            
            if filters:
                if 'category' in filters:
                    search_params['SearchIndex'] = filters['category']
                if 'min_price' in filters:
                    search_params['MinimumPrice'] = int(filters['min_price'] * 100)
                if 'max_price' in filters:
                    search_params['MaximumPrice'] = int(filters['max_price'] * 100)
                if 'sort' in filters:
                    search_params['Sort'] = filters['sort']
                if 'condition' in filters:
                    search_params['Condition'] = filters['condition']
                if filters.get('prime_eligible'):
                    search_params['Prime'] = 'true'
                if 'brand' in filters:
                    search_params['Brand'] = filters['brand']

            # Make API request
            response = self.amazon.ItemSearch(**search_params)
            
            # Parse response
            items = self._parse_response(response)
            
            # Convert to ProductInfo objects
            products = []
            for item in items:
                product_info = self._extract_product_info(item)
                if product_info:
                    # Apply post-filtering
                    if filters:
                        if 'min_rating' in filters and product_info.rating < filters['min_rating']:
                            continue
                        if filters.get('free_shipping') and not product_info.shipping_info['is_free_shipping']:
                            continue
                    products.append(product_info)
            
            return products

        except Exception as e:
            print(f"Error searching Amazon products: {str(e)}")
            return []

    def search_by_asin(self, asin: str) -> Optional[ProductInfo]:
        """
        Get detailed product information by ASIN
        
        Args:
            asin (str): Amazon Standard Identification Number
            
        Returns:
            Optional[ProductInfo]: Product information if found
        """
        try:
            response = self.amazon.ItemLookup(
                ItemId=asin,
                ResponseGroup='Large'
            )
            
            items = self._parse_response(response)
            if items:
                return self._extract_product_info(items[0])
            return None
            
        except Exception as e:
            print(f"Error looking up ASIN {asin}: {str(e)}")
            return None

