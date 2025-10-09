from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from db.db_manager import DatabaseManager, get_database
from schema.brand import BrandResponse
from app.utils.mongo import fix_mongo_types

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=List[BrandResponse])
async def get_brands(db: DatabaseManager = Depends(get_database)):
    """Get all active brands"""
    try:
        brands = await db.find_many("brands", {"is_active": True}, sort=[("name", 1)])
        serialize_brands = []
        # Fix ObjectId serialization
        for brand in brands:
            if brand:
                brand = fix_mongo_types(brand)
                serialize_brands.append(brand)
        
        return serialize_brands

    except Exception as e:
        logger.error(f"Get brands error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get brands"    
        )