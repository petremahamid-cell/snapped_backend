from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import logging
import json

from app.db.base import get_db
from app.models.schemas import (
    ImageUploadResponse, ImageClipResponse, SimilarProductsResponse, 
    SearchResult, ImageClipRequest, SearchListResponse, ProductFilter,
    ImageSearch
)
from app.utils.image_processing import (
    save_upload_file, clip_image, is_allowed_file, 
    get_image_dimensions, optimize_image
)
from app.services.serpapi_service import search_similar_products
from app.services.db_service import (
    create_image_search, create_search_results, get_search_by_id, 
    get_recent_searches, get_search_count, get_filtered_results
)
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    optimize: bool = Form(False),
    max_size: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload an image for product search
    
    Args:
        file: The image file to upload
        optimize: Whether to optimize the image for web use
        max_size: Maximum dimension (width or height) in pixels for optimization
        db: Database session
        
    Returns:
        ImageUploadResponse with the path to the uploaded image
    """
    try:
        # Save the uploaded file
        upload_result = await save_upload_file(file)
        file_path = upload_result["file_path"]
        logger.info(f"Image uploaded: {file_path}")
        
        # Optimize the image if requested
        if optimize:
            # Check if file_path is a URL (Cloudinary) or a local path
            if file_path.startswith(('http://', 'https://')):
                # For Cloudinary URLs, we can't optimize locally
                logger.info(f"Skipping local optimization for Cloudinary URL: {file_path}")
                # We could implement Cloudinary transformations here if needed
            else:
                # Only optimize local files
                file_path = await optimize_image(file_path, max_size)
                logger.info(f"Image optimized: {file_path}")
        
        return {
            "image_path": file_path, 
            "cloudinary_public_id": upload_result.get("cloudinary_public_id"),
            "cloudinary_url": upload_result.get("cloudinary_url"),
            "message": "Image uploaded successfully"
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

@router.post("/clip", response_model=ImageClipResponse)
async def clip_uploaded_image(
    clip_request: Optional[ImageClipRequest] = None,
    clip_request_str: Optional[str] = Form(None),
    cloudinary_public_id: Optional[str] = Form(None),
    # Individual form fields for direct form submission
    image_path: Optional[str] = Form(None),
    x: Optional[int] = Form(None),
    y: Optional[int] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None)
):
    """
    Clip an uploaded image to the specified dimensions
    
    This endpoint supports three ways to provide the clipping parameters:
    1. As a JSON body with clip_request object
    2. As a form field with clip_request_str containing a JSON string
    3. As individual form fields (image_path, x, y, width, height)
    
    Args:
        clip_request: Request containing image path and clipping coordinates (JSON body)
        clip_request_str: JSON string representation of clip_request (form field)
        cloudinary_public_id: Cloudinary public ID of the original image
        image_path, x, y, width, height: Individual form fields for direct form submission
        
    Returns:
        ImageClipResponse with the path to the clipped image
    """
    # Determine which input method was used and create a clip_request object
    if clip_request is None:
        if clip_request_str:
            # Parse the JSON string from form field
            try:
                import json
                clip_data = json.loads(clip_request_str)
                clip_request = ImageClipRequest(**clip_data)
                logger.info(f"Using clip_request from JSON string: {clip_request}")
            except Exception as e:
                logger.error(f"Error parsing clip_request_str: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid clip_request JSON: {str(e)}")
        elif image_path and x is not None and y is not None and width is not None and height is not None:
            # Use individual form fields
            clip_request = ImageClipRequest(
                image_path=image_path,
                x=x,
                y=y,
                width=width,
                height=height
            )
            logger.info(f"Using clip_request from individual form fields: {clip_request}")
        else:
            raise HTTPException(
                status_code=400, 
                detail="Missing clip parameters. Provide either clip_request as JSON body, "
                       "clip_request_str as form field with JSON string, or individual form fields."
            )
    
    # Check if the file exists (only for local paths)
    if not clip_request.image_path.startswith(('http://', 'https://')) and not os.path.exists(clip_request.image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        # Get image dimensions for validation
        img_width, img_height = await get_image_dimensions(clip_request.image_path)
        
        # Validate coordinates
        if (clip_request.x < 0 or clip_request.y < 0 or 
            clip_request.x + clip_request.width > img_width or 
            clip_request.y + clip_request.height > img_height):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid crop coordinates. Image dimensions: {img_width}x{img_height}"
            )
        
        # Clip the image
        clip_result = await clip_image(
            clip_request.image_path, 
            clip_request.x, 
            clip_request.y, 
            clip_request.width, 
            clip_request.height,
            cloudinary_public_id
        )
        
        logger.info(f"Image clipped: {clip_result['file_path']}")
        
        return {
            "image_path": clip_result["file_path"], 
            "original_image_path": clip_request.image_path,
            "cloudinary_public_id": clip_result.get("cloudinary_public_id"),
            "cloudinary_url": clip_result.get("cloudinary_url"),
            "original_cloudinary_public_id": clip_result.get("original_cloudinary_public_id"),
            "message": "Image clipped successfully"
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error clipping image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clipping image: {str(e)}")

# Alternative endpoint with form data for compatibility
@router.post("/clip-form", response_model=ImageClipResponse)
async def clip_uploaded_image_form(
    image_path: str = Form(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    cloudinary_public_id: Optional[str] = Form(None)
):
    """
    Clip an uploaded image to the specified dimensions using form data
    
    This is a simplified endpoint that only accepts individual form fields.
    For more options, use the /clip endpoint.
    """
    # Pass the parameters directly to the main clip endpoint
    return await clip_uploaded_image(
        clip_request=None,
        clip_request_str=None,
        cloudinary_public_id=cloudinary_public_id,
        image_path=image_path,
        x=x,
        y=y,
        width=width,
        height=height
    )

@router.post("/search", response_model=SimilarProductsResponse)
async def search_products(
    image_path: str = Form(...),
    original_image_path: Optional[str] = Form(None),
    is_clipped: bool = Form(False),
    cloudinary_public_id: Optional[str] = Form(None),
    cloudinary_url: Optional[str] = Form(None),
    original_cloudinary_public_id: Optional[str] = Form(None),
    original_cloudinary_url: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Search for similar products using the uploaded image
    
    This endpoint is optimized for fast response times by:
    1. Using background tasks for database operations
    2. Caching search results
    3. Implementing retries with exponential backoff
    4. Running CPU-intensive operations in a thread pool
    
    Args:
        image_path: Path to the image to search with
        original_image_path: Path to the original image before clipping (if applicable)
        is_clipped: Whether the image was clipped
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        SimilarProductsResponse with search results
    """
    # Check if the file exists (only for local paths)
    if not image_path.startswith(('http://', 'https://')) and not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        # Create a new search record
        db_search = await create_image_search(
            db, 
            image_path, 
            original_image_path, 
            is_clipped,
            cloudinary_public_id,
            cloudinary_url,
            original_cloudinary_public_id,
            original_cloudinary_url
        )
        
        # Use Cloudinary URL if available, otherwise use local path
        if cloudinary_url:
            image_url = cloudinary_url
            logger.info(f"Using Cloudinary URL for search: {image_url}")
        else:
            # Convert local file path to URL for SerpAPI
            public = settings.PUBLIC_BASE_URL.strip('/') if settings.PUBLIC_BASE_URL else f"https://{settings.HOST}:{settings.PORT}"
            image_url = f"{public}/static/uploads/{os.path.basename(image_path)}"
            logger.info(f"Using local URL for search: {image_url}")
        
        logger.info(f"Searching for products with image: {image_url}")
        
        # Search for similar products (this is cached and optimized)
        similar_products = await search_similar_products(image_url)
        
        # Log the number of products returned from search
        logger.info(f"search_similar_products returned {len(similar_products)} products")
        
        # Store search results in the database as a background task
        # This allows us to return the response to the user faster
        # while the database operations continue in the background
        background_tasks.add_task(
            create_search_results, db, db_search.id, similar_products
        )
        
        # Convert results to schema models
        # We don't need to wait for the database operation to complete
        results = [
            SearchResult(
                id=0,  # Temporary ID since we're not waiting for DB
                search_id=db_search.id,
                title=product.get("title"),
                link=product.get("link"),
                image_url=product.get("image_url"),
                price=product.get("price"),
                brand=product.get("brand"),
                source=product.get("source"),
                description=product.get("description"),
                rating=product.get("rating"),
                reviews_count=product.get("reviews_count")
            )
            for product in similar_products
        ]
        
        logger.info(f"Found {len(results)} similar products")
        
        return {
            "search_id": db_search.id,
            "search_time": db_search.search_time,
            "image_path": db_search.image_path,
            "original_image_path": db_search.original_image_path,
            "is_clipped": db_search.is_clipped,
            "cloudinary_public_id": db_search.cloudinary_public_id,
            "cloudinary_url": db_search.cloudinary_url,
            "original_cloudinary_public_id": db_search.original_cloudinary_public_id,
            "original_cloudinary_url": db_search.original_cloudinary_url,
            "results": results,
            "total_results": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching for products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for products: {str(e)}")

@router.get("/searches/{search_id}", response_model=SimilarProductsResponse)
async def get_search_results(
    search_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the results of a previous search
    
    Args:
        search_id: ID of the search
        db: Database session
        
    Returns:
        SimilarProductsResponse with search results
    """
    # Get the search record
    db_search = await get_search_by_id(db, search_id)
    
    if not db_search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Get all results for this search
    results_data = db_search.results
    sorted_results = sorted(results_data, key=lambda x: x.id)  # Sort by 'id' if needed
    logger.info(f"Retrieved {len(sorted_results)} results for search ID: {search_id}")
    
    # Convert DB results to schema models
    results = [
        SearchResult(
            id=result.id,
            search_id=result.search_id,
            title=result.title,
            link=result.link,
            image_url=result.image_url,
            price=result.price,
            brand=result.brand,
            source=result.source,
            description=result.description,
            rating=result.rating,
            reviews_count=result.reviews_count
        )
        for result in sorted_results
    ]
    
    return {
        "search_id": db_search.id,
        "search_time": db_search.search_time,
        "image_path": db_search.image_path,
        "original_image_path": db_search.original_image_path,
        "is_clipped": db_search.is_clipped,
        "cloudinary_public_id": db_search.cloudinary_public_id,
        "cloudinary_url": db_search.cloudinary_url,
        "original_cloudinary_public_id": db_search.original_cloudinary_public_id,
        "original_cloudinary_url": db_search.original_cloudinary_url,
        "results": results,
        "total_results": len(results)
    }

@router.get("/searches", response_model=SearchListResponse)
async def get_recent_search_results(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    include_results: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Get recent search results with pagination
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_results: Whether to include search results
        db: Database session
        
    Returns:
        SearchListResponse with paginated search results
    """
    # Get recent searches
    db_searches = await get_recent_searches(db, skip, limit, include_results)
    total = await get_search_count(db)
    
    # Convert DB searches to schema models
    searches = []
    for db_search in db_searches:
        if include_results:
            results = [
                SearchResult(
                    id=result.id,
                    search_id=result.search_id,
                    title=result.title,
                    link=result.link,
                    image_url=result.image_url,
                    price=result.price,
                    brand=result.brand,
                    source=result.source,
                    description=result.description,
                    rating=result.rating,
                    reviews_count=result.reviews_count
                )
                for result in db_search.results
            ]
        else:
            results = []
        
        searches.append(
            ImageSearch(
                id=db_search.id,
                image_path=db_search.image_path,
                original_image_path=db_search.original_image_path,
                is_clipped=db_search.is_clipped,
                search_time=db_search.search_time,
                cloudinary_public_id=db_search.cloudinary_public_id,
                cloudinary_url=db_search.cloudinary_url,
                original_cloudinary_public_id=db_search.original_cloudinary_public_id,
                original_cloudinary_url=db_search.original_cloudinary_url,
                results=results
            )
        )
    
    logger.info(f"Retrieved {len(searches)} searches (total: {total})")
    
    return {
        "searches": searches,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit
    }

@router.get("/dimensions/{image_path:path}")
async def get_dimensions(image_path: str):
    """
    Get the dimensions of an image
    
    Args:
        image_path: Path to the image
        
    Returns:
        Dictionary with width and height
    """
    # Check if the file exists (only for local paths)
    if not image_path.startswith(('http://', 'https://')) and not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        width, height = await get_image_dimensions(image_path)
        return {"width": width, "height": height}
    except Exception as e:
        logger.error(f"Error getting image dimensions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting image dimensions: {str(e)}")