import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
import os
from dotenv import load_dotenv
import base64
from typing import List, Dict, Optional, Any
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

class CloudinaryManager:
    """Enhanced Cloudinary manager for multiple image operations"""
    
    @staticmethod
    def initialize():
        """Initialize and validate Cloudinary configuration"""
        required_vars = ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"Missing Cloudinary environment variables: {missing_vars}")
            return False
        
        logger.info("Cloudinary initialized successfully")
        return True
    
    @staticmethod
    async def upload_image(
        image_data: str,
        folder: str = "uploads",
        public_id: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Upload single image to Cloudinary with multiple size variants
        
        Args:
            image_data: Base64 encoded image data (with or without data URI prefix)
            folder: Cloudinary folder to upload to
            public_id: Custom public ID for the image
            **kwargs: Additional Cloudinary upload parameters
            
        Returns:
            Dict with upload result including multiple size URLs
        """
        try:
            if not CloudinaryManager.initialize():
                logger.error("Cloudinary not properly configured")
                return None
            
            # Clean base64 data
            if image_data.startswith('data:'):
                image_data = image_data.split(',', 1)[1]
            
            # Validate base64 data
            try:
                decoded = base64.b64decode(image_data)
                if len(decoded) < 1024:  # Less than 1KB
                    logger.error("Image data too small")
                    return None
                if len(decoded) > 10 * 1024 * 1024:  # More than 10MB
                    logger.error("Image data too large")
                    return None
            except Exception as decode_error:
                logger.error(f"Invalid base64 data: {decode_error}")
                return None
            
            # Prepare upload parameters
            upload_params = {
                "folder": folder,
                "quality": "auto:good",
                "fetch_format": "auto",
                "flags": "progressive",
                "resource_type": "image",
                **kwargs
            }
            
            if public_id:
                upload_params["public_id"] = public_id
                upload_params["overwrite"] = True
            
            # Upload to Cloudinary
            logger.info(f"Uploading image to Cloudinary folder: {folder}")
            
            result = cloudinary.uploader.upload(
                f"data:image/auto;base64,{image_data}",
                **upload_params
            )
            
            logger.info(f"Image uploaded successfully: {result.get('public_id')}")
            
            # Generate multiple size URLs for responsive images
            base_public_id = result["public_id"]
            
            urls = {
                "original": result["secure_url"],
                "thumbnail": CloudinaryManager.get_transformed_url(
                    base_public_id, 
                    width=150, 
                    height=150, 
                    crop="fill",
                    gravity="center"
                ),
                "small": CloudinaryManager.get_transformed_url(
                    base_public_id, 
                    width=300, 
                    height=300, 
                    crop="fill",
                    gravity="center"
                ),
                "medium": CloudinaryManager.get_transformed_url(
                    base_public_id, 
                    width=600, 
                    height=400, 
                    crop="fill",
                    gravity="center"
                ),
                "large": CloudinaryManager.get_transformed_url(
                    base_public_id, 
                    width=1200, 
                    height=800, 
                    crop="fit"
                )
            }
            
            return {
                "public_id": result["public_id"],
                "urls": urls,
                "url": result["secure_url"],  # For backward compatibility
                "secure_url": result["secure_url"],  # For backward compatibility
                "format": result.get("format", "jpg"),
                "width": result.get("width", 0),
                "height": result.get("height", 0),
                "bytes": result.get("bytes", 0),
                "created_at": result.get("created_at", "")
            }
            
        except Exception as e:
            logger.error(f"Error uploading image to Cloudinary: {e}")
            return None
    
    @staticmethod
    def get_transformed_url(public_id: str, **transformation_options) -> str:
        """Get transformed image URL with optimizations"""
        # Add default optimizations
        transformation_options.update({
            "quality": "auto:good",
            "fetch_format": "auto",
            "flags": "progressive"
        })
        
        url, _ = cloudinary_url(public_id, **transformation_options)
        return url
    
    @staticmethod
    async def delete_image(public_id: str) -> bool:
        """Delete image from Cloudinary"""
        try:
            if not CloudinaryManager.initialize():
                return False
            
            result = cloudinary.uploader.destroy(public_id)
            
            if result.get("result") == "ok":
                logger.info(f"Image deleted from Cloudinary: {public_id}")
                return True
            else:
                logger.warning(f"Failed to delete image: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting image from Cloudinary: {e}")
            return False
    
    @staticmethod
    async def upload_multiple_images(
        images_data: List[str],
        folder: str = "uploads",
        product_id: Optional[str] = None,
        progress_callback = None
    ) -> List[Dict[str, Any]]:
        """
        Upload multiple images to Cloudinary with progress tracking
        
        Args:
            images_data: List of base64 encoded image data
            folder: Cloudinary folder to upload to
            product_id: Optional product ID for naming
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of upload results
        """
        uploaded_images = []
        
        for i, image_data in enumerate(images_data):
            try:
                # Generate public_id with index
                public_id = f"{folder}_{product_id}_{i}" if product_id else None
                
                # Call progress callback if provided
                if progress_callback:
                    progress = (i + 1) / len(images_data) * 100
                    await progress_callback(f"Uploading image {i + 1} of {len(images_data)}", progress)
                
                result = await CloudinaryManager.upload_image(
                    image_data,
                    folder=folder,
                    public_id=public_id
                )
                
                if result:
                    # Add index and primary flag to result
                    result.update({
                        "index": i,
                        "is_primary": i == 0
                    })
                    uploaded_images.append(result)
                    logger.info(f"Successfully uploaded image {i + 1}")
                else:
                    logger.error(f"Failed to upload image {i + 1}")
                    
            except Exception as e:
                logger.error(f"Error uploading image {i + 1}: {e}")
                continue
        
        logger.info(f"Successfully uploaded {len(uploaded_images)} out of {len(images_data)} images")
        return uploaded_images
    
    @staticmethod
    async def delete_multiple_images(public_ids: List[str]) -> Dict[str, bool]:
        """
        Delete multiple images from Cloudinary
        
        Args:
            public_ids: List of public IDs to delete
            
        Returns:
            Dict mapping public_id to success status
        """
        results = {}
        
        for public_id in public_ids:
            try:
                success = await CloudinaryManager.delete_image(public_id)
                results[public_id] = success
            except Exception as e:
                logger.error(f"Error deleting image {public_id}: {e}")
                results[public_id] = False
        
        successful_deletes = sum(1 for success in results.values() if success)
        logger.info(f"Deleted {successful_deletes} out of {len(public_ids)} images")
        
        return results
    
    @staticmethod
    def validate_image_data(image_data: str) -> bool:
        """Validate base64 image data"""
        try:
            if not image_data or not isinstance(image_data, str):
                return False
            
            # Check if it's a data URI
            if image_data.startswith('data:image/'):
                image_data = image_data.split(',', 1)[1]
            
            # Validate base64
            decoded = base64.b64decode(image_data)
            
            # Check minimum size (1KB) and maximum size (10MB)
            if len(decoded) < 1024 or len(decoded) > 10 * 1024 * 1024:
                return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    async def reorder_product_images(product_id: str, image_order: List[int], db) -> bool:
        """
        Reorder product images based on provided index order
        
        Args:
            product_id: Product ID
            image_order: List of indices representing new order
            db: Database manager
            
        Returns:
            True if successful, False otherwise
        """
        try:
            product = await db.find_one("products", {"_id": ObjectId(product_id)})
            if not product:
                return False
            
            current_images = product.get("images", [])
            if not current_images:
                return True
            
            # Reorder images based on provided order
            reordered_images = []
            for new_index, old_index in enumerate(image_order):
                if 0 <= old_index < len(current_images):
                    image = current_images[old_index].copy()
                    image["index"] = new_index
                    image["is_primary"] = new_index == 0
                    reordered_images.append(image)
            
            # Update product with reordered images
            await db.update_one(
                "products",
                {"_id": ObjectId(product_id)},
                {"$set": {"images": reordered_images}}
            )
            
            logger.info(f"Reordered images for product {product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error reordering product images: {e}")
            return False