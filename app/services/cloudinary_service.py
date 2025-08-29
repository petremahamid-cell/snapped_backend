import logging
import os
from typing import Dict, Optional, Tuple

from app.core.config import settings

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

# Only import cloudinary if it's enabled
if settings.USE_CLOUDINARY:
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api
        CLOUDINARY_AVAILABLE = True
    except ImportError:
        logger.warning("Cloudinary package not installed. Using local storage instead.")
        CLOUDINARY_AVAILABLE = False
else:
    CLOUDINARY_AVAILABLE = False


def upload_image(image_path: str, folder: str = "snapped_ai") -> Dict:
    """
    Upload an image to Cloudinary.
    
    Args:
        image_path: Path to the image file
        folder: Cloudinary folder to store the image in
        
    Returns:
        Dict containing upload result with public_id, secure_url, etc.
    """
    # Normalize the image path
    image_path = normalize_path(image_path)
      
    if not CLOUDINARY_AVAILABLE or not settings.USE_CLOUDINARY:
        logger.warning("Cloudinary not available or disabled. Using local storage.")
        return {
            "public_id": None,
            "secure_url": None,
            "original_filename": os.path.basename(image_path),
            "format": os.path.splitext(image_path)[1].lstrip('.'),
            "width": 0,
            "height": 0,
            "bytes": 0,
            "resource_type": "image",
            "created_at": None,
            "tags": [],
            "url": image_path,
        }
    
    try:
        logger.info(f"Uploading image to Cloudinary: {image_path}")
        # Ensure the file exists
        if not os.path.exists(image_path):
            logger.error(f"File not found: {image_path}")
            raise FileNotFoundError(f"File not found: {image_path}")
            
        result = cloudinary.uploader.upload(
            image_path,
            folder=folder,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        logger.info(f"Image uploaded successfully to Cloudinary: {result['public_id']}")
        return result
    except Exception as e:
        logger.error(f"Error uploading image to Cloudinary: {str(e)}", exc_info=True)
        # Return a fallback response with local path
        return {
            "public_id": None,
            "secure_url": None,
            "original_filename": os.path.basename(image_path),
            "format": os.path.splitext(image_path)[1].lstrip('.'),
            "width": 0,
            "height": 0,
            "bytes": 0,
            "resource_type": "image",
            "created_at": None,
            "tags": [],
            "url": image_path,
        }


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary.
    
    Args:
        public_id: Cloudinary public ID of the image
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    if not CLOUDINARY_AVAILABLE or not settings.USE_CLOUDINARY or not public_id:
        logger.warning("Cloudinary not available or disabled. Skipping image deletion.")
        return False
    
    try:
        logger.info(f"Deleting image from Cloudinary: {public_id}")
        result = cloudinary.uploader.destroy(public_id)
        if result.get("result") == "ok":
            logger.info(f"Image deleted successfully from Cloudinary: {public_id}")
            return True
        else:
            logger.warning(f"Failed to delete image from Cloudinary: {public_id}, result: {result}")
            return False
    except Exception as e:
        logger.error(f"Error deleting image from Cloudinary: {str(e)}", exc_info=True)
        return False


def get_image_url(public_id: Optional[str], local_path: str) -> str:
    """
    Get the URL for an image, either from Cloudinary or local storage.
    
    Args:
        public_id: Cloudinary public ID of the image
        local_path: Local path to the image
        
    Returns:
        str: URL to the image
    """
    if not CLOUDINARY_AVAILABLE or not settings.USE_CLOUDINARY or not public_id:
        # Return local path
        if local_path.startswith('/'):
            # Convert absolute path to relative URL
            base_path = os.path.join(settings.STATIC_FOLDER, 'uploads')
            if local_path.startswith(base_path):
                rel_path = local_path[len(base_path):].lstrip('/')
                return f"/static/uploads/{rel_path}"
        return local_path
    
    try:
        # Return Cloudinary URL
        return cloudinary.CloudinaryImage(public_id).build_url(secure=True)
    except Exception as e:
        logger.error(f"Error getting Cloudinary URL: {str(e)}", exc_info=True)
        return local_path


def transform_image(public_id: str, width: int = 300, height: int = 300, crop: str = "fill") -> str:
    """
    Generate a transformed image URL from Cloudinary.
    
    Args:
        public_id: Cloudinary public ID of the image
        width: Desired width
        height: Desired height
        crop: Crop mode (fill, limit, etc.)
        
    Returns:
        str: URL to the transformed image
    """
    if not CLOUDINARY_AVAILABLE or not settings.USE_CLOUDINARY or not public_id:
        logger.warning("Cloudinary not available or disabled. Cannot transform image.")
        return ""
    
    try:
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=width,
            height=height,
            crop=crop,
            secure=True
        )
    except Exception as e:
        logger.error(f"Error transforming image with Cloudinary: {str(e)}", exc_info=True)
        return ""


def crop_image(public_id: str, x: int, y: int, width: int, height: int, folder: str = "snapped_ai_clipped") -> Dict:
    """
    Crop an image in Cloudinary using the explicit method with eager transformations.
    
    Args:
        public_id: Cloudinary public ID of the image to crop
        x: X coordinate of the top-left corner
        y: Y coordinate of the top-left corner
        width: Width of the cropped area
        height: Height of the cropped area
        folder: Cloudinary folder to store the cropped image
        
    Returns:
        Dict containing the result with public_id, secure_url, etc.
    """
    if not CLOUDINARY_AVAILABLE or not settings.USE_CLOUDINARY or not public_id:
        logger.warning("Cloudinary not available or disabled. Cannot crop image.")
        return {
            "public_id": None,
            "secure_url": None,
            "resource_type": "image",
            "created_at": None,
            "tags": [],
            "url": "",
        }
    
    try:
        logger.info(f"Cropping image in Cloudinary: {public_id}, x={x}, y={y}, width={width}, height={height}")
        
        # Create a new cropped version with a unique name
        crop_transformation = {
            "crop": "crop",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        
        # Generate a new public_id for the cropped image
        basename = os.path.basename(public_id)
        basename = normalize_path(basename)
        new_public_id = f"{folder}/{basename}_cropped"
        
        
        # Create a new cropped image using the explicit method with eager transformations
        result = cloudinary.uploader.explicit(
            public_id,
            type="upload",
            eager=[crop_transformation],
            eager_async=False,
            eager_notification_url=None
        )
        
        # If eager transformation was successful, get the transformed URL
        if result and "eager" in result and len(result["eager"]) > 0:
            # Create a new image with the cropped version
            upload_result = cloudinary.uploader.upload(
                result["eager"][0]["secure_url"],
                public_id=new_public_id,
                overwrite=True
            )
            logger.info(f"Image cropped successfully in Cloudinary: {upload_result['public_id']}")
            return upload_result
        else:
            # Fallback: create a URL with transformation parameters
            transformed_url = cloudinary.CloudinaryImage(public_id).build_url(
                transformation=[crop_transformation],
                secure=True
            )
            
            # Upload the transformed image as a new image
            upload_result = cloudinary.uploader.upload(
                transformed_url,
                public_id=new_public_id,
                overwrite=True
            )
            logger.info(f"Image cropped successfully in Cloudinary (fallback): {upload_result['public_id']}")
            return upload_result
            
    except Exception as e:
        logger.error(f"Error cropping image in Cloudinary: {str(e)}", exc_info=True)
        return {
            "public_id": None,
            "secure_url": None,
            "resource_type": "image",
            "created_at": None,
            "tags": [],
            "url": "",
        }
