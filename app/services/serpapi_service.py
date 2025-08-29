import httpx
import json
import asyncio
import os
import re
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.utils.performance import timed_async, run_in_threadpool
from app.utils.connection_pool import get_http_client

# Set up logging
logger = logging.getLogger(__name__)

# Use Redis cache in production, fallback to in-memory cache in development
if os.getenv("REDIS_ENABLED", "false").lower() == "true":
    from app.utils.redis_cache import redis_cache
    cache_decorator = redis_cache(ttl=3600)
else:
    from app.utils.performance import async_cache
    cache_decorator = async_cache(ttl=3600)

# --- Regex helpers ---
PRICE_PATTERN = re.compile(
    r'(?:[\$£€¥₹]|USD|EUR|GBP|JPY|INR)\s*\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d+)?'
    r'|\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d+)?\s*(?:USD|EUR|GBP|JPY|INR)'
)
BRAND_PATTERNS = [
    re.compile(r'^([\w\s]+?)\s+[-–|]'),            # Brand at the beginning followed by separator
    re.compile(r'by\s+([\w\s]+)', re.IGNORECASE),  # "by Brand"
    re.compile(r'from\s+([\w\s]+)', re.IGNORECASE) # "from Brand"
]

# --- Price helpers ---
def normalize_price(price_str: str) -> Optional[str]:
    """Normalize price strings for better comparison."""
    if not price_str:
        return None

    # Remove extra whitespace and normalize
    price_str = re.sub(r'\s+', ' ', price_str.strip())

    # Extract price with currency symbol
    price_match = re.search(r'[\$€£¥₹]\s*[\d,]+\.?\d*', price_str)
    if price_match:
        return price_match.group()

    # Extract price without currency symbol
    price_match = re.search(r'\d+[,.]?\d*', price_str)
    if price_match:
        return price_match.group()

    return price_str

def extract_price_from_text(text: Optional[str]) -> Optional[str]:
    """Try to pull a price-like token out of arbitrary text."""
    if not text:
        return None
    return normalize_price(text)

def extract_brand_from_title(title: str) -> Optional[str]:
    """Best-effort brand extraction from a title string."""
    if not title:
        return None
    for pattern in BRAND_PATTERNS:
        match = pattern.search(title)
        if match:
            return match.group(1).strip()
    # Fallback: first word if Capitalized
    words = title.split()
    if words and words[0] and words[0][0].isupper():
        return words[0]
    return None

# --- Normalize Title to Remove Unwanted Parts ---
def normalize_title(title: str) -> str:
    """
    Normalize the title to remove irrelevant parts for better comparison.
    This includes removing 'Similar Item' and product variant details like size or color.
    """
    if not title:
        return title
    
    # Remove the "Similar Item" and other dynamic parts of the title
    title = re.sub(r'\(Similar Item \d+\)', '', title)  # Remove "Similar Item X"
    title = re.sub(r'\s*\([^\)]*\)', '', title)         # Remove any parenthesis-based details (like sizes, etc.)
    title = re.sub(r'\s+', ' ', title).strip()          # Clean up extra spaces
    
    return title.lower()  # Use lowercase for a case-insensitive comparison

# --- Deduplication function ---
def filter_duplicates(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out duplicate products from the list.
    Products are considered duplicates if they have the same normalized title.
    """
    seen = set()
    unique_products = []

    for product in products:
        # Normalize the title to remove irrelevant parts
        normalized_title = normalize_title(product.get("title", ""))

        # Add product to the result if it hasn't been seen before
        if normalized_title not in seen:
            unique_products.append(product)
            seen.add(normalized_title)
            
    return unique_products

@timed_async
@cache_decorator  # Cache results for 1 hour
async def search_similar_products(image_url: str) -> List[Dict[str, Any]]:
    """
    Search for similar products using SerpAPI's Google Lens.

    Args:
        image_url: Public URL of the image to search (for local files, first upload to storage/CDN)

    Returns:
        List of similar products with title, link, image_url, price, brand, rating, reviews_count, source
    """
    api_url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_lens",
        "url": image_url,                    # SerpAPI accepts a URL for Google Lens
        "api_key": settings.SERPAPI_API_KEY,
        "hl": "en",
        "gl": "us"
    }

    client = await get_http_client()
    for attempt in range(3):
        try:
            logger.info(f"Making Google Lens request for image: {image_url}")
            response = await client.get(api_url, params=params)

            if response.status_code != 200:
                raise Exception(
                    f"Google Lens request failed with status {response.status_code}: {response.text}"
                )

            data = response.json()
            products = await process_google_lens_response(data)

            if not products:
                logger.warning(f"No products found for image: {image_url}")
                return []

            # Filter products where price is not available
            products_with_price = [product for product in products if product.get("price")]
            
            logger.info(f"Found {len(products_with_price)} products with valid prices from Google Lens")
            return products_with_price

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == 2:
                logger.error(f"Google Lens request failed after 3 attempts: {str(e)}")
                raise
            wait_time = 2 ** attempt  # 1, 2, 4 seconds
            logger.warning(f"Google Lens request failed (attempt {attempt+1}/3). Retrying in {wait_time}s: {str(e)}")
            await asyncio.sleep(wait_time)

async def process_google_lens_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process the SerpAPI Google Lens response to extract product information.
    """
    products: List[Dict[str, Any]] = []

    # Check for API error
    if "error" in data:
        logger.error(f"SerpAPI error: {data['error']}")
        return []

    logger.info(f"Google Lens response keys: {list(data.keys())}")

    # Primary: visual_matches (best for product discovery)
    visual_matches = data.get("visual_matches", []) or []
    logger.info(f"Found {len(visual_matches)} items in visual_matches")
    for item in visual_matches:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        price_value = item.get("price", {}).get("value", "")

        product = {
            "title": title,
            "link": item.get("link", "") or item.get("source", "") or "",
            "image_url": item.get("thumbnail", "") or item.get("original", "") or "",
            "price": price_value,
            "brand": extract_brand_from_title(title),
            "source": "visual_matches",
            "description": snippet,
            "rating": item.get("rating") if isinstance(item.get("rating"), (int, float)) else None,
            "reviews_count": item.get("reviews") or item.get("reviews_count") or None,
        }
        products.append(product)

    # Secondary: shopping_results (usually structured product/price data)
    shopping_results = data.get("shopping_results", []) or []
    logger.info(f"Found {len(shopping_results)} items in shopping_results")
    for item in shopping_results:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        # Normalize explicit price first, then fall back to title/snippet
        price = normalize_price(item.get("price", "")) \
                or extract_price_from_text(title) \
                or extract_price_from_text(snippet)

        product = {
            "title": title or "Unknown Product",
            "link": item.get("link", "") or "",
            "image_url": item.get("thumbnail", "") or "",
            "price": price,
            "brand": item.get("source") or extract_brand_from_title(title) or "",
            "source": "shopping_results",
            "description": snippet,
            "rating": item.get("rating") if isinstance(item.get("rating"), (int, float)) else None,
            "reviews_count": item.get("reviews") or item.get("reviews_count") or None,
        }
        products.append(product)

    # Deduplicate using thread pool to avoid blocking event loop
    unique_products = await run_in_threadpool(filter_duplicates, products)
    logger.info(f"Products after deduplication: {len(unique_products)}")

    # Filter out products without a valid price
    products_with_price = [product for product in unique_products if product.get("price")]

    # If no valid products, log it and return an empty list
    if not products_with_price:
        logger.warning(f"No valid products with price found. Returning empty list.")
        return []
    # Enforce max cap
    return products_with_price[:settings.MAX_SIMILAR_PRODUCTS]

def extract_product_info(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize product info for storage/response.
    """
    return {
        "title": product.get("title", ""),
        "link": product.get("link", ""),
        "image_url": product.get("image_url", ""),
        "price": product.get("price", ""),
        "brand": product.get("brand", ""),
        "source": product.get("source", ""),
        "description": product.get("description", ""),
        "rating": product.get("rating", None),
        "reviews_count": product.get("reviews_count", None),
        "raw_data": json.dumps(product) if getattr(settings, "STORE_RAW_DATA", False) else None,
    }
