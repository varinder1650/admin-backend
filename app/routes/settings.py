from fastapi import APIRouter, Depends, HTTPException, status
import logging
from db.db_manager import DatabaseManager, get_database

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/public")
async def get_public_settings(db: DatabaseManager = Depends(get_database)):
    """Get public app settings"""
    try:
        # Get app settings from database
        settings = await db.find_one("pricing_config", {})
        # print(settings)
        if not settings:
            # Return default settings if none exist
            default_settings = {
                "app_name": "SmartBag",
                "app_version": "1.0.0",
                "currency": "USD",
                "tax_rate": 0.08,
                "shipping_fee": 5.00,
                "free_shipping_threshold": 50.00,
                "contact_email": "support@smartbag.com",
                "contact_phone": "+1234567890",
                "social_media": {
                    "facebook": "",
                    "instagram": "",
                    "twitter": ""
                },
                "payment_methods": ["card", "paypal", "apple_pay"],
                "delivery_areas": ["City Center", "Suburbs", "Downtown"]
            }
            return default_settings
        
        # Remove sensitive data if any
        settings.pop("_id", None)
        # settings.pop("type", None)
        
        return settings

    except Exception as e:
        logger.error(f"Get public settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get app settings"
        )