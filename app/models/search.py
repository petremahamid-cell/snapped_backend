from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class ImageSearch(Base):
    __tablename__ = "image_searches"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)
    original_image_path = Column(String, nullable=True)  # Path to the original image before clipping
    search_time = Column(DateTime, default=datetime.utcnow, index=True)
    is_clipped = Column(Boolean, default=False)  # Whether the image was clipped
    
    # Cloudinary fields
    cloudinary_public_id = Column(String, nullable=True)  # Cloudinary public ID
    cloudinary_url = Column(String, nullable=True)  # Cloudinary URL
    original_cloudinary_public_id = Column(String, nullable=True)  # Original image Cloudinary public ID
    original_cloudinary_url = Column(String, nullable=True)  # Original image Cloudinary URL
    
    # Relationship with search results
    results = relationship("SearchResult", back_populates="search", cascade="all, delete-orphan")
    
    # Create indexes for faster queries
    __table_args__ = (
        Index('ix_image_searches_search_time_desc', search_time.desc()),
    )

class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("image_searches.id"), index=True)
    
    # Product information
    title = Column(String, nullable=True)
    link = Column(String, nullable=True)
    image_url = Column(String, nullable=True)  # URL to the product image
    price = Column(String, nullable=True, index=True)  # Price as string to handle different currencies
    brand = Column(String, nullable=True, index=True)  # Brand name
    source = Column(String, nullable=True)  # Source of the product (inline_images, image_results, shopping_results)
    
    # Additional metadata
    description = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    
    # Raw data for future reference (can be disabled in settings)
    raw_data = Column(Text, nullable=True)
    
    # Relationship with search
    search = relationship("ImageSearch", back_populates="results")
    
    # Create indexes for faster queries
    __table_args__ = (
        Index('ix_search_results_price_brand', price, brand),
    )