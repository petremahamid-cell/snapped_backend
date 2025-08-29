import os
import uuid
import logging
from typing import Tuple, Optional, Dict, Any
from PIL import Image
from fastapi import UploadFile, HTTPException
import aiofiles
from app.core.config import settings
from app.utils.performance import run_in_threadpool
from app.services.cloudinary_service import upload_image, get_image_url

# Set up logging
logger = logging.getLogger(__name__)

def normalize_path(path: str) -> str:
    """
    Normalize a path to use forward slashes and ensure it's a valid path
    
    Args:
        path: The path to normalize
        
    Returns:
        Normalized path
    """
    # Replace backslashes with forward slashes
    normalized = path.replace('\\', '/')
    # Remove any double slashes
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    return normalized
    
async def save_upload_file(upload_file: UploadFile) -> Dict[str, Any]:
    """
    Save an uploaded file to Cloudinary or local storage
    
    Args:
        upload_file: The uploaded file
        
    Returns:
        Dict containing file path and Cloudinary info
    """
    # Check if the file is allowed
    if not is_allowed_file(upload_file.filename):
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    
    try:
        # Read file content
        content = await upload_file.read()
        
        # Check file size
        if len(content) > settings.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size: {settings.MAX_CONTENT_LENGTH / 1024 / 1024}MB")
        
        # Generate a unique filename
        file_extension = os.path.splitext(upload_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        # Normalize the filename to use forward slashes
        unique_filename = normalize_path(unique_filename)
        
        # Try to upload to Cloudinary first if enabled
        cloudinary_result = None
        if settings.USE_CLOUDINARY:
            try:
                # Create a temporary file for Cloudinary upload
                # Use normalized path for temp file
                temp_dir = "/tmp"
                os.makedirs(temp_dir, exist_ok=True)
                temp_file_path = normalize_path(os.path.join(temp_dir, unique_filename))
                logger.info(f"Creating temporary file at: {temp_file_path}")
                async with aiofiles.open(temp_file_path, 'wb') as temp_file:
                    await temp_file.write(content)
                
                # Upload to Cloudinary
                cloudinary_result = await run_in_threadpool(
                    lambda: upload_image(temp_file_path, folder="snapped_ai_uploads")
                )
                
                # Remove temporary file
                os.remove(temp_file_path)
                
                logger.info(f"File uploaded to Cloudinary: {cloudinary_result.get('public_id')}")
                
                # If Cloudinary upload is successful and we're using Cloudinary exclusively,
                # we don't need to save the file locally
                if not settings.SAVE_LOCAL_COPY:
                    return {
                        "file_path": cloudinary_result.get("secure_url"),  # Use Cloudinary URL as file path
                        "cloudinary_public_id": cloudinary_result.get("public_id"),
                        "cloudinary_url": cloudinary_result.get("secure_url")
                    }
            except Exception as e:
                logger.error(f"Error uploading to Cloudinary: {str(e)}")
                # If Cloudinary is required but failed, raise an exception
                if settings.REQUIRE_CLOUDINARY:
                    raise HTTPException(status_code=500, detail=f"Error uploading to Cloudinary: {str(e)}")
                # Otherwise, continue with local file
        
        # Save locally if Cloudinary is not enabled, failed, or we want a local copy
        # Create uploads directory if it doesn't exist
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        file_path = normalize_path(os.path.join(settings.UPLOAD_FOLDER, unique_filename))
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            # Seek to the beginning if we've already read the content
            if upload_file.file.tell() > 0:
                await upload_file.seek(0)
                content = await upload_file.read()
            await out_file.write(content)
        
        logger.info(f"File saved locally: {file_path}")
        
        return {
            "file_path": file_path,
            "cloudinary_public_id": cloudinary_result.get("public_id") if cloudinary_result else None,
            "cloudinary_url": cloudinary_result.get("secure_url") if cloudinary_result else None
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

async def clip_image(image_path: str, x: int, y: int, width: int, height: int, 
                original_cloudinary_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Clip an image to the specified dimensions
    
    Args:
        image_path: Path to the image
        x: X coordinate of the top-left corner
        y: Y coordinate of the top-left corner
        width: Width of the clipped area
        height: Height of the clipped area
        original_cloudinary_id: Cloudinary public ID of the original image
        
    Returns:
        Dict containing file path and Cloudinary info
    """
    # Validate input parameters
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="Width and height must be positive")
    
    try:
        # Check if we can use Cloudinary's cropping functionality directly
        if settings.USE_CLOUDINARY and original_cloudinary_id:
            try:
                # Use Cloudinary's transformation API to crop the image
                from app.services.cloudinary_service import crop_image
                
                cloudinary_result = await run_in_threadpool(
                    lambda: crop_image(original_cloudinary_id, x, y, width, height, folder="snapped_ai_clipped")
                )
                
                logger.info(f"Image clipped directly in Cloudinary: {cloudinary_result.get('public_id')}")
                
                # If we're using Cloudinary exclusively, return the Cloudinary URL as the file path
                if not settings.SAVE_LOCAL_COPY:
                    return {
                        "file_path": cloudinary_result.get("secure_url"),
                        "cloudinary_public_id": cloudinary_result.get("public_id"),
                        "cloudinary_url": cloudinary_result.get("secure_url"),
                        "original_cloudinary_public_id": original_cloudinary_id
                    }
            except Exception as e:
                logger.error(f"Error clipping image in Cloudinary: {str(e)}")
                # If Cloudinary is required but failed, raise an exception
                if settings.REQUIRE_CLOUDINARY:
                    raise HTTPException(status_code=500, detail=f"Error clipping image in Cloudinary: {str(e)}")
                # Otherwise, continue with local processing
        
        # Process locally if Cloudinary direct cropping is not available or failed
        clipped_image_path = await run_in_threadpool(
            _clip_image_sync, image_path, x, y, width, height
        )
        logger.info(f"Image clipped locally: {clipped_image_path}")
        
        # Upload to Cloudinary if enabled
        cloudinary_result = None
        if settings.USE_CLOUDINARY:
            try:
                cloudinary_result = await run_in_threadpool(
                    lambda: upload_image(clipped_image_path, folder="snapped_ai_clipped")
                )
                logger.info(f"Clipped image uploaded to Cloudinary: {cloudinary_result.get('public_id')}")
                
                # If we're using Cloudinary exclusively and don't need local copies,
                # we can remove the local file after uploading to Cloudinary
                if not settings.SAVE_LOCAL_COPY:
                    os.remove(clipped_image_path)
                    return {
                        "file_path": cloudinary_result.get("secure_url"),
                        "cloudinary_public_id": cloudinary_result.get("public_id"),
                        "cloudinary_url": cloudinary_result.get("secure_url"),
                        "original_cloudinary_public_id": original_cloudinary_id
                    }
            except Exception as e:
                logger.error(f"Error uploading clipped image to Cloudinary: {str(e)}")
                # If Cloudinary is required but failed, raise an exception
                if settings.REQUIRE_CLOUDINARY:
                    raise HTTPException(status_code=500, detail=f"Error uploading clipped image to Cloudinary: {str(e)}")
                # Otherwise, continue with local file
        
        return {
            "file_path": clipped_image_path,
            "cloudinary_public_id": cloudinary_result.get("public_id") if cloudinary_result else None,
            "cloudinary_url": cloudinary_result.get("secure_url") if cloudinary_result else None,
            "original_cloudinary_public_id": original_cloudinary_id
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error clipping image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clipping image: {str(e)}")

def _clip_image_sync(image_path: str, x: int, y: int, width: int, height: int) -> str:
    """
    Synchronous version of clip_image for use with run_in_threadpool
    """
    # Open the image
    img = Image.open(image_path)
    
    # Validate coordinates
    img_width, img_height = img.size
    if x < 0 or y < 0 or x + width > img_width or y + height > img_height:
        raise ValueError(f"Invalid crop coordinates. Image dimensions: {img_width}x{img_height}")
    
    # Clip the image
    clipped_img = img.crop((x, y, x + width, y + height))
    
    # Generate a new filename for the clipped image
    file_name, file_extension = os.path.splitext(os.path.basename(image_path))
    clipped_filename = f"{file_name}_clipped{file_extension}"

    # Ensure the upload folder exists
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    clipped_image_path = normalize_path(os.path.join(settings.UPLOAD_FOLDER, clipped_filename))
    
    # Save the clipped image
    clipped_img.save(clipped_image_path)
    
    return clipped_image_path

async def get_image_dimensions(image_path: str) -> Tuple[int, int]:
    """
    Get the dimensions of an image
    
    Args:
        image_path: Path to the image or URL
        
    Returns:
        Tuple of (width, height)
    """
    try:
        # Handle URLs (including Cloudinary URLs)
        if image_path.startswith(('http://', 'https://')):
            import httpx
            import io
            
            # Download the image
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(image_path)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Could not download image from URL: {image_path}"
                    )
                
                # Open the image from bytes
                dimensions = await run_in_threadpool(
                    lambda: Image.open(io.BytesIO(response.content)).size
                )
        else:
            # Local file path
            if not os.path.exists(image_path):
                raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
                
            dimensions = await run_in_threadpool(
                lambda: Image.open(image_path).size
            )
            
        return dimensions
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting image dimensions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting image dimensions: {str(e)}")

async def optimize_image(image_path: str, max_size: Optional[int] = None) -> str:
    """
    Optimize an image for web use
    
    Args:
        image_path: Path to the image (must be a local file path, not a URL)
        max_size: Maximum dimension (width or height) in pixels
        
    Returns:
        Path to the optimized image
    """
    # Validate that image_path is a local file path, not a URL
    if image_path.startswith(('http://', 'https://')):
        logger.error(f"Cannot optimize a URL directly: {image_path}")
        raise HTTPException(
            status_code=400, 
            detail="Cannot optimize a URL directly. For Cloudinary images, use Cloudinary transformations instead."
        )
    
    # Check if the file exists
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
    
    try:
        optimized_path = await run_in_threadpool(
            _optimize_image_sync, image_path, max_size
        )
        logger.info(f"Image optimized successfully: {optimized_path}")
        return optimized_path
    except Exception as e:
        logger.error(f"Error optimizing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error optimizing image: {str(e)}")

def _optimize_image_sync(image_path: str, max_size: Optional[int] = None) -> str:
    """
    Synchronous version of optimize_image for use with run_in_threadpool
    """
    # Open the image
    img = Image.open(image_path)
    
    # Resize if needed
    if max_size:
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Generate a new filename for the optimized image
    file_name, file_extension = os.path.splitext(os.path.basename(image_path))
    optimized_filename = f"{file_name}_optimized{file_extension}"
    
    # Ensure the upload folder exists
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    optimized_path = normalize_path(os.path.join(settings.UPLOAD_FOLDER, optimized_filename))
    
    # Save the optimized image with reduced quality
    if file_extension.lower() in ['.jpg', '.jpeg']:
        img.save(optimized_path, quality=85, optimize=True)
    elif file_extension.lower() == '.png':
        img.save(optimized_path, optimize=True)
    else:
        img.save(optimized_path)
    
    return optimized_path

def is_allowed_file(filename: str) -> bool:
    """
    Check if a file has an allowed extension
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the file has an allowed extension, False otherwise
    """
    if not filename:
        return False
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS
