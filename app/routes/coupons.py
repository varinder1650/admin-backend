from typing import Dict
from bson import ObjectId
from fastapi import APIRouter, Depends

from admin.utils.serialize import serialize_document
from app.utils.auth import current_active_user
from schema.user import UserinDB
from db.db_manager import DatabaseManager, get_database

router = APIRouter()

@router.post("/validate")
async def validate_coupon(coupon_data:Dict,current_user:UserinDB = Depends(current_active_user),db: DatabaseManager = Depends(get_database)):
    try:
        valid = False
        code = coupon_data["code"]
        amount = coupon_data["order_amount"]
        result = await db.find_one("discount_coupons",{"code":code,"is_active":True})
        if result:
            if result['usage_limit'] == 0:
                valid = False
                return {
                    "valid": valid,
                    "promocode": serialize_document(result)
                }
            if amount >= result['min_order_amount']:
                valid = True
            if result['target_audience'] == 'all_users':
                valid = True
            elif result['target_audience'] == 'specific_users':
                if str(current_user.id) not in result['specific_users']:
                    valid = False
                else:
                    valid = True
            elif result['target_audience'] == 'new_users':
                new_user = await db.find_one('orders',{'user':ObjectId(current_user.id)})
                if new_user:
                    valid = False
                else:
                    valid = True
        return {
            "valid": valid,
            "promocode": serialize_document(result)
        }
    except Exception as e:
        raise e