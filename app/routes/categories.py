from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from db.db_manager import DatabaseManager, get_database
from schema.category import CategoryResponse
from app.utils.mongo import fix_mongo_types

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db: DatabaseManager = Depends(get_database)):
    """Get all active categories"""
    try:
        # Add better error handling and filters
        categories = await db.find_many(
            "categories", 
            {"is_active": True},  # Only get active categories
            sort=[("name", 1)]
        )
        
        print(categories)
        # Fix ObjectId serialization and handle empty results
        processed_categories = []
        for category in categories:
            if category:
                # Use the mongo fix utility
                fixed_category = fix_mongo_types(category)
                processed_categories.append(fixed_category)
        
        return processed_categories

    except Exception as e:
        logger.error(f"Get categories error: {e}")
        # Log the full traceback for debugging
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get categories"    
        )