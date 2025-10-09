from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, Query
import logging
from app.utils.auth import current_active_user
from app.utils.mongo import fix_mongo_types
from db.db_manager import DatabaseManager, get_database
from schema.cart import CartRequest, UpdateCartItemRequest
from schema.user import UserinDB
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

def process_product_images_for_cart(product):
    """Convert admin panel image objects to mobile app compatible URLs"""
    images = product.get("images", [])
    processed_images = []
    
    if isinstance(images, list):
        for img in images:
            if isinstance(img, dict):
                # Image object from admin panel/Cloudinary
                url = img.get("url") or img.get("secure_url") or img.get("original")
                if url:
                    processed_images.append(url)
            elif isinstance(img, str) and img.strip():
                # Direct URL string
                processed_images.append(img)
    elif isinstance(images, str) and images.strip():
        # Single image string (backward compatibility)
        processed_images.append(images)
    
    return processed_images

@router.post("/add")
async def add_to_cart(
    req: CartRequest, 
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)    
):
    product_id = req.productId
    quantity = req.quantity
    try:
        logger.info(f"Adding product {product_id} to cart for user {current_user.email}")
        
        if not ObjectId.is_valid(product_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product ID"
            )
            
        # Find the product
        product = await db.find_one("products", {
            "_id": ObjectId(product_id),
            "is_active": True
        })
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
            
        if product['stock'] < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough stock available"
            )
        
        # Find or create cart
        cart = await db.find_one("carts", {"user": ObjectId(current_user.id)})

        if not cart:
            # Create new cart
            item_id = str(uuid.uuid4())
            cart_data = {
                "user": ObjectId(current_user.id),
                "items": [{
                    "_id": item_id,
                    "product": ObjectId(product_id), 
                    "quantity": quantity,
                    "added_at": datetime.utcnow()
                }],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.insert_one("carts", cart_data)
            logger.info(f"Created new cart for user {current_user.email}")
        else:
            # Update existing cart
            existing_item = None
            for item in cart["items"]:
                if item["product"] == ObjectId(product_id):
                    existing_item = item
                    break
                    
            if existing_item:
                # Update quantity
                existing_item["quantity"] += quantity
                existing_item["updated_at"] = datetime.utcnow()
            else:
                # Add new item
                item_id = str(uuid.uuid4())
                cart["items"].append({
                    "_id": item_id,
                    "product": ObjectId(product_id), 
                    "quantity": quantity,
                    "added_at": datetime.utcnow()
                })

            cart["updated_at"] = datetime.utcnow()
            await db.update_one(
                "carts", 
                {"_id": cart["_id"]},
                {
                    "$set": {
                        "items": cart["items"],
                        "updated_at": cart["updated_at"]
                    }
                }
            )
            logger.info(f"Updated cart for user {current_user.email}")
            
        return {"message": "Product added to cart successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to cart: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to cart"
        )

@router.get("/")
async def get_cart(
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Getting cart for user {current_user.email}")
        
        cart = await db.find_one("carts", {"user": ObjectId(current_user.id)})

        if not cart:
            return {"items": []}
        
        items_with_products = []
        for item in cart.get('items', []):
            try:
                # Get product details with populated references
                pipeline = [
                    {"$match": {"_id": item["product"], "is_active": True}},
                    {
                        "$lookup": {
                            "from": "categories",
                            "localField": "category",
                            "foreignField": "_id",
                            "as": "category_data"
                        }
                    },
                    {
                        "$lookup": {
                            "from": "brands",
                            "localField": "brand",
                            "foreignField": "_id",
                            "as": "brand_data"
                        }
                    },
                    {
                        "$addFields": {
                            "category": {
                                "$ifNull": [
                                    {"$arrayElemAt": ["$category_data", 0]},
                                    {"name": "Uncategorized", "_id": None}
                                ]
                            },
                            "brand": {
                                "$ifNull": [
                                    {"$arrayElemAt": ["$brand_data", 0]},
                                    {"name": "No Brand", "_id": None}
                                ]
                            }
                        }
                    },
                    {
                        "$project": {
                            "category_data": 0,
                            "brand_data": 0
                        }
                    }
                ]
                
                products_result = await db.aggregate("products", pipeline)
                
                if products_result:
                    product = products_result[0]
                    product_fixed = fix_mongo_types(product)
                    
                    # Process images for mobile app
                    product_fixed["images"] = process_product_images_for_cart(product_fixed)
                    
                    # Ensure cart item has proper ID
                    item_id = item.get("_id") or str(uuid.uuid4())
                    
                    items_with_products.append({
                        "_id": item_id,
                        "product": product_fixed,
                        "quantity": item.get("quantity", 0),
                        "added_at": item.get("added_at"),
                        "updated_at": item.get("updated_at")
                    })
                else:
                    logger.warning(f"Product {item['product']} not found or inactive")
                    
            except Exception as item_error:
                logger.error(f"Error processing cart item: {item_error}")
                continue
        
        logger.info(f"Returning {len(items_with_products)} cart items for user {current_user.email}")
        return {"items": items_with_products}
        
    except Exception as e:
        logger.error(f"Get cart error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cart"
        )

@router.put("/update")
async def update_cart_item(
    req: UpdateCartItemRequest,
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    item_id = req.itemId
    quantity = req.quantity
    try:
        logger.info(f"Updating cart item {item_id} to quantity {quantity} for user {current_user.email}")
        
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity must be greater than 0"
            )
            
        cart = await db.find_one("carts", {"user": ObjectId(current_user.id)})
        if not cart:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart not found"
            )
        
        # Find and update item
        item_found = False
        for item in cart["items"]:
            if str(item.get("_id", "")) == item_id:
                # Check if product is in stock
                product = await db.find_one("products", {"_id": item["product"], "is_active": True})
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Product not found or inactive"
                    )
                if product["stock"] < quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Not enough stock available"
                    )
                item["quantity"] = quantity
                item["updated_at"] = datetime.utcnow()
                item_found = True
                break
                
        if not item_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in cart"
            )
        
        # Update cart
        await db.update_one(
            "carts",
            {"_id": cart["_id"]},
            {
                "$set": {
                    "items": cart["items"],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Cart item {item_id} updated successfully")
        return {"message": "Cart item updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cart"
        )

@router.delete("/remove")
async def remove_from_cart(
    item_id: str = Query(..., description="Cart item ID to remove"),
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    """Remove item from cart"""
    try:
        logger.info(f"Removing cart item {item_id} for user {current_user.email}")
        
        cart = await db.find_one("carts", {"user": ObjectId(current_user.id)})
        if not cart:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart not found"
            )
        
        # Find and remove item
        original_count = len(cart["items"])
        cart["items"] = [item for item in cart["items"] if str(item.get("_id", "")) != item_id]
        
        if len(cart["items"]) == original_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in cart"
            )
        
        # Update cart
        await db.update_one(
            "carts",
            {"_id": cart["_id"]},
            {
                "$set": {
                    "items": cart["items"],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Cart item {item_id} removed successfully")
        return {"message": "Item removed from cart"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove from cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from cart"
        )

@router.delete("/clear")
async def clear_cart(
    current_user: UserinDB = Depends(current_active_user),
    db: DatabaseManager = Depends(get_database)
):
    """Clear user's cart"""
    try:
        logger.info(f"Clearing cart for user {current_user.email}")
        
        cart = await db.find_one("carts", {"user": ObjectId(current_user.id)})
        if not cart:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart not found"
            )
        
        # Clear cart items
        await db.update_one(
            "carts",
            {"_id": cart["_id"]},
            {
                "$set": {
                    "items": [],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Cart cleared successfully for user {current_user.email}")
        return {"message": "Cart cleared successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear cart error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cart"
        )