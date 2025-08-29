from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from typing import List, Dict, Any, Optional, Tuple
from app.models.search import ImageSearch, SearchResult
from app.models.schemas import ProductFilter
from app.services.serpapi_service import extract_product_info
import logging

# Set up logging
logger = logging.getLogger(__name__)

async def create_image_search(
    db: Session, 
    image_path: str, 
    original_image_path: Optional[str] = None,
    is_clipped: bool = False,
    cloudinary_public_id: Optional[str] = None,
    cloudinary_url: Optional[str] = None,
    original_cloudinary_public_id: Optional[str] = None,
    original_cloudinary_url: Optional[str] = None
) -> ImageSearch:
    """
    Create a new image search record
    
    Args:
        db: Database session
        image_path: Path to the uploaded image
        original_image_path: Path to the original image before clipping
        is_clipped: Whether the image was clipped
        cloudinary_public_id: Cloudinary public ID of the image
        cloudinary_url: Cloudinary URL of the image
        original_cloudinary_public_id: Cloudinary public ID of the original image
        original_cloudinary_url: Cloudinary URL of the original image
        
    Returns:
        Created ImageSearch object
    """
    db_search = ImageSearch(
        image_path=image_path,
        original_image_path=original_image_path,
        is_clipped=is_clipped,
        cloudinary_public_id=cloudinary_public_id,
        cloudinary_url=cloudinary_url,
        original_cloudinary_public_id=original_cloudinary_public_id,
        original_cloudinary_url=original_cloudinary_url
    )
    db.add(db_search)
    db.commit()
    db.refresh(db_search)
    return db_search

async def create_search_results(db: Session, search_id: int, products: List[Dict[str, Any]]) -> List[SearchResult]:
    """
    Create search result records for a search
    
    Args:
        db: Database session
        search_id: ID of the associated search
        products: List of product dictionaries
        
    Returns:
        List of created SearchResult objects
    """
    db_results = []
    
    for product in products:
        product_info = extract_product_info(product)
        db_result = SearchResult(search_id=search_id, **product_info)
        db.add(db_result)
        db_results.append(db_result)
    
    db.commit()
    
    # Refresh all results to get their IDs
    for result in db_results:
        db.refresh(result)
    
    logger.info(f"Created {len(db_results)} search results for search ID {search_id}")
    return db_results

async def get_search_by_id(db: Session, search_id: int) -> Optional[ImageSearch]:
    """
    Get an image search by ID
    
    Args:
        db: Database session
        search_id: ID of the search
        
    Returns:
        ImageSearch object if found, None otherwise
    """
    return db.query(ImageSearch).filter(ImageSearch.id == search_id).first()

async def get_recent_searches(
    db: Session, 
    skip: int = 0, 
    limit: int = 10,
    include_results: bool = False
) -> List[ImageSearch]:
    """
    Get recent image searches
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_results: Whether to include search results
        
    Returns:
        List of ImageSearch objects
    """
    query = db.query(ImageSearch).order_by(ImageSearch.search_time.desc())
    
    if include_results:
        query = query.options(
            joinedload(ImageSearch.results)
        )
    
    return query.offset(skip).limit(limit).all()

async def get_search_count(db: Session) -> int:
    """
    Get the total number of searches
    
    Args:
        db: Database session
        
    Returns:
        Total number of searches
    """
    return db.query(func.count(ImageSearch.id)).scalar()

async def get_filtered_results(
    db: Session,
    search_id: int,
    filters: ProductFilter,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[SearchResult], int]:
    """
    Get filtered search results for a search
    
    Args:
        db: Database session
        search_id: ID of the search
        filters: Filter criteria
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        Tuple of (list of SearchResult objects, total count)
    """
    query = db.query(SearchResult).filter(SearchResult.search_id == search_id)
    
    # Apply filters
    if filters:
        if filters.brand:
            brand_filters = [SearchResult.brand.ilike(f"%{brand}%") for brand in filters.brand]
            query = query.filter(or_(*brand_filters))
        
        if filters.price_min is not None or filters.price_max is not None:
            # This is a simplified approach - in a real app, you'd need to handle currency conversion
            # and proper numeric comparison
            if filters.price_min is not None:
                query = query.filter(SearchResult.price.op('REGEXP')(f'[0-9]+(\.[0-9]+)? >= {filters.price_min}'))
            
            if filters.price_max is not None:
                query = query.filter(SearchResult.price.op('REGEXP')(f'[0-9]+(\.[0-9]+)? <= {filters.price_max}'))
        
        if filters.source:
            query = query.filter(SearchResult.source.in_(filters.source))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    results = query.offset(skip).limit(limit).all()
    
    return results, total