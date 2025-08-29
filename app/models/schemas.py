from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

# Search Result Schema
class SearchResultBase(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[str] = None
    brand: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None

class SearchResultCreate(SearchResultBase):
    raw_data: Optional[str] = None

class SearchResult(SearchResultBase):
    id: int
    search_id: int
    
    class Config:
        orm_mode = True
        from_attributes = True

# Image Search Schema
class ImageSearchBase(BaseModel):
    image_path: str
    original_image_path: Optional[str] = None
    is_clipped: bool = False
    cloudinary_public_id: Optional[str] = None
    cloudinary_url: Optional[str] = None
    original_cloudinary_public_id: Optional[str] = None
    original_cloudinary_url: Optional[str] = None

class ImageSearchCreate(ImageSearchBase):
    pass

class ImageSearch(ImageSearchBase):
    id: int
    search_time: datetime
    results: List[SearchResult] = []
    
    class Config:
        orm_mode = True
        from_attributes = True

# Request Schemas
class ImageClipRequest(BaseModel):
    image_path: str
    x: int
    y: int
    width: int
    height: int

# Response Schemas
class ImageUploadResponse(BaseModel):
    image_path: str
    cloudinary_public_id: Optional[str] = None
    cloudinary_url: Optional[str] = None
    message: str = "Image uploaded successfully"

class ImageClipResponse(BaseModel):
    image_path: str
    original_image_path: str
    cloudinary_public_id: Optional[str] = None
    cloudinary_url: Optional[str] = None
    original_cloudinary_public_id: Optional[str] = None
    original_cloudinary_url: Optional[str] = None
    message: str = "Image clipped successfully"

class SimilarProductsResponse(BaseModel):
    search_id: int
    search_time: datetime
    image_path: str
    original_image_path: Optional[str] = None
    is_clipped: bool
    cloudinary_public_id: Optional[str] = None
    cloudinary_url: Optional[str] = None
    original_cloudinary_public_id: Optional[str] = None
    original_cloudinary_url: Optional[str] = None
    results: List[SearchResult]
    total_results: int

# API Schemas for all searches
class SearchListResponse(BaseModel):
    searches: List[ImageSearch]
    total: int
    page: int
    page_size: int

# Filter schemas
class ProductFilter(BaseModel):
    brand: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    source: Optional[List[str]] = None