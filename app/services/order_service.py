
from datetime import datetime
from bson import ObjectId
from db.db_manager import DatabaseManager
from schema.order import OrderCreate


class OrderService:
    def __init__(self,db:DatabaseManager):
        self.db = db
    
    async def create_order(self, order_data:dict, current_user):
        if not order_data.get('items'):
            raise ValueError("Order item are required")

        if not order_data.get('delivery_address'):
            raise ValueError("address not found")

        if not order_data.get('total_amount') or order_data['total_amount'] <= 0:
            raise ValueError("valid total amount is required")
        
        order_data['user'] = current_user.id
        order_data['accepter_partners'] = []
        
        try:
            validated_order = OrderCreate(**order_data)
        except Exception as Validation_error:
            raise ValueError(f"Invalid order data {str(Validation_error)}")
        
        for item in validated_order.items:
            product = await self.db.find_one("products", {"_id": ObjectId(item.product)})
            if not product:
                raise ValueError(f"Product not found: {item.product}")
            if product["stock"] < item.quantity:
                raise ValueError(f"Insufficient stock for product: {product['name']}")
        
        # Decrement stock for all products
        for item in validated_order.items:
            await self.db.update_one(
                "products",
                {"_id": ObjectId(item.product)},
                {"$inc": {"stock": -item.quantity}}
            )
        
        # Create order
        order_dict = validated_order.dict()
        order_dict["user"] = ObjectId(current_user.id)
        order_dict["status_change_history"] = [{
            "status": "pending",
            "changed_at": datetime.utcnow(),
            "changed_by": current_user.name or "Customer"
        }]
        # Ensure created_at and updated_at are set
        now = datetime.utcnow()
        order_dict["created_at"] = order_dict.get("created_at", now)
        order_dict["updated_at"] = order_dict.get("updated_at", now)
        order_dict["promo_code"] = order_data['promo_code']
        order_dict["promo_discount"] = order_data['promo_discount']
        # print("order data: ", order_dict)
        order_id = await self.db.insert_one("orders", order_dict)
        
        if order_data['promo_code']:
            update_coupon = await self.db.find_one("discount_coupons",{"code":order_data['promo_code']})
            if update_coupon['usage_limit'] > 0:
                await self.db.update_one('discount_coupons',{"code":order_data['promo_code']},{"usage_limit":update_coupon['usage_limit']-1})
        # Clear user's cart
        cart = await self.db.find_one("carts", {"user": ObjectId(current_user.id)})
        if cart:
            await self.db.update_one(
                "carts",
                {"_id": cart["_id"]},
                {"$set": {"items": []}}
            )
        
        return order_id