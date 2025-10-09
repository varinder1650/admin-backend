from fastapi import WebSocket, WebSocketDisconnect, status
from admin.connection_manager import manager
from admin.auth import verify_admin_token, authenticate_admin
from db.db_manager import get_database
import logging
from admin.handlers.products import send_products, create_product, delete_product, update_product
from admin.handlers.brand import send_brands, create_brand, update_brand, delete_brand
from admin.handlers.orders import send_orders,update_order_status,get_delivery_requests_for_order,assign_delivery_partner,get_orders_for_download
from admin.handlers.category import send_categories, create_categories, update_category, delete_category
from admin.handlers.customers import send_customers
from admin.handlers.help import get_tickets,get_ticket_detail,get_ticket_stats,update_ticket_status,respond_to_ticket
from admin.handlers.requests import get_requests,update_requests_status
from admin.handlers.coupons import get_coupons,create_coupons,update_coupon,delete_coupon,toggle_coupon
from admin.handlers.auth import (
    handle_get_users, 
    handle_update_user_role, 
    handle_update_user_status
)
from admin.handlers.settings import (
    send_inventory_status, 
    handle_get_analytics, 
    get_pricing_config, 
    update_pricing_config
)

logger = logging.getLogger(__name__)

async def admin_websocket_handler(websocket: WebSocket):
    """Single WebSocket endpoint for all admin functionality"""
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    user_info = None
    authenticated = False
    
    try:
        # Authentication phase
        auth_message = await websocket.receive_json()
        logger.info(f"Auth message received: {auth_message}")
        
        # Extract credentials from payload
        payload = auth_message.get('payload', {})
        email = payload.get("email")
        password = payload.get("password") 
        token = payload.get("token")
        
        # Try different authentication methods
        if email and password:
            # Initial login with credentials
            logger.info(f"Authenticating with email/password: {email}")
            user_info = await authenticate_admin({"email": email, "password": password})
            
        elif token:
            # Token-based authentication (reconnection)
            logger.info("Authenticating with token")
            user_info = await verify_admin_token(token)
            
        else:
            logger.error("No valid authentication credentials provided")
            await websocket.send_json({
                "type": "error", 
                "message": "No valid authentication credentials provided"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Check authentication result
        if not user_info:
            logger.error("Authentication failed - no user info returned")
            await websocket.send_json({
                "type": "error", 
                "message": "Authentication failed"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Check for authentication errors (token expired, etc.)
        if isinstance(user_info, dict) and user_info.get("error"):
            logger.error(f"Authentication error: {user_info['error']}")
            await websocket.send_json({
                "type": "error",
                "message": f"Authentication failed: {user_info['error']}"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        logger.info(f"Authentication successful for user: {user_info.get('email', 'unknown')}")
        
        # Register connection
        await manager.connect(websocket, user_info)
        authenticated = True
        
        # Send success response
        await websocket.send_json({
            "type": "auth_success",
            "user": user_info
        })
        logger.info("Auth success message sent")
        
        # Main message handling loop
        await handle_admin_messages(websocket, user_info)
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
        if authenticated and user_info:
            manager.disconnect(websocket)
            logger.info(f"Admin {user_info.get('email', 'unknown')} disconnected")
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        if authenticated:
            manager.disconnect(websocket)
            
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

async def handle_admin_messages(websocket: WebSocket, user_info: dict):
    """Handle all admin messages through unified connection"""
    
    db = get_database()
    subscriptions = set()
    
    logger.info(f"Message handler started for user: {user_info.get('email', 'unknown')}")
    
    while True:
        try:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            logger.info(f"Received message type: {msg_type}")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif msg_type == "subscribe":
                channel = message.get("channel")
                if channel in ["products", "orders", "customers", "brands", "categories", "users"]:
                    subscriptions.add(channel)
                    await manager.subscribe(websocket, channel)
                    await send_initial_data(websocket, channel, db)
            
            elif msg_type == "unsubscribe":
                channel = message.get("channel")
                subscriptions.discard(channel)
                await manager.unsubscribe(websocket, channel)
            
            # Products handlers
            elif msg_type == "get_products":
                # Check if client is still connected before processing
                if websocket.client_state.value == 1:
                    await send_products(websocket, db)
                else:
                    logger.info("Client disconnected before processing get_products")
            
            elif msg_type == "create_product":
                if websocket.client_state.value == 1:
                    await create_product(websocket, message.get("data"), user_info, db)
            
            elif msg_type == "update_product":
                if websocket.client_state.value == 1:
                    await update_product(websocket, message.get("data"), user_info, db)
            
            elif msg_type == "delete_product":
                if websocket.client_state.value == 1:
                    await delete_product(websocket, message.get("data"), user_info, db)
           
            # Orders handlers
            elif msg_type == "get_orders":
                await send_orders(websocket, message.get("filters", {}), db)
            
            elif msg_type == "update_order_status":
                await update_order_status(websocket,message.get("data"),user_info,db)

            elif msg_type == "get_delivery_requests_for_order":
                await get_delivery_requests_for_order(websocket,message.get("data"),db)

            elif msg_type == "assign_delivery_partner":
                await assign_delivery_partner(websocket,message.get("data"),db)
                
            # Categories handlers
            elif msg_type == "get_categories":
                await send_categories(websocket, db)
            
            elif msg_type == "create_category":
                await create_categories(websocket, message.get("data"), user_info, db)

            elif msg_type == "update_category":
                await update_category(websocket, message.get("data"), user_info, db)
            
            elif msg_type == "delete_category":
                await delete_category(websocket, message.get("data"), user_info, db)
                
            # Brands handlers
            elif msg_type == "get_brands":
                await send_brands(websocket, db)
            
            elif msg_type == "create_brand":
                await create_brand(websocket, message.get("data"), user_info, db)

            elif msg_type == "update_brand":
                await update_brand(websocket, message.get("data"), user_info, db)
            
            elif msg_type == "delete_brand":
                await delete_brand(websocket, message.get("data"), user_info, db)

            # Users handlers
            elif msg_type == "get_users":
                await handle_get_users(websocket, message.get("filters", {}), db)

            elif msg_type == "update_user_role":
                await handle_update_user_role(websocket, message.get("data"), user_info, db)

            elif msg_type == "update_user_status":
                await handle_update_user_status(websocket, message.get("data"), user_info, db)

            # Analytics handlers
            elif msg_type == "get_analytics":
                await handle_get_analytics(websocket, message.get("data", {}), db)

            # Pricing handlers
            elif msg_type == "get_pricing_config":
                await get_pricing_config(websocket, db)
                
            elif msg_type == "update_pricing_config":
                await update_pricing_config(websocket, message.get("data"), user_info, db)

            # Settings handlers
            elif msg_type == "get_inventory_status":
                await send_inventory_status(websocket, db)

            # Customers handlers
            elif msg_type == "get_customers":
                await send_customers(websocket, db)

            #Support tickets
            elif msg_type == "get_help_tickets":
                await get_tickets(websocket,message.get("filters",{}),db)
            
            elif msg_type == "get_ticket_detail":
                ticket_id = message.get("ticket_id")
                if ticket_id:
                    await get_ticket_detail(websocket, {"ticket_id": ticket_id}, db)
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Ticket ID required for detail view"
                    })
                    
            elif msg_type == "respond_to_ticket":
                await respond_to_ticket(websocket, message.get("data"), db)
                
            elif msg_type == "update_ticket_status":
                await update_ticket_status(websocket, message.get("data"), db)
                
            elif msg_type == "get_ticket_stats":
                await get_ticket_stats(websocket, message.get("data"), db)

            #User suggestion requests
            elif msg_type == "get_user_suggestions":
                await get_requests(websocket,message.get("filters",{}),db)
            
            elif msg_type == "update_suggestion_status":
                await update_requests_status(websocket,message.get("data"),db)

            #Discount coupons
            elif msg_type == "create_discount_coupon":
                await create_coupons(websocket,message.get("data"),db)
            
            elif msg_type == "get_discount_coupons":
                await get_coupons(websocket,db)

            elif msg_type == "update_discount_coupon":
                await update_coupon(websocket,message.get("data"),db)
            
            elif msg_type == "delete_discount_coupon":
                await delete_coupon(websocket,message.get("data"),db)

            elif msg_type == "toggle_coupon_status":
                await toggle_coupon(websocket,message.get("data"),db)

            #Logout
            elif msg_type == "logout":
                logger.info(f"User {user_info.get('email')} logging out")
                break

            else:
                logger.warning(f"Unknown message type: {msg_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })
                
        except WebSocketDisconnect:
            logger.info(f"Admin {user_info.get('email', 'unknown')} disconnected during message handling")
            break
            
        except Exception as e:
            logger.error(f"Error handling message {msg_type if 'msg_type' in locals() else 'unknown'}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Internal server error: {str(e)}"
                })
            except:
                # Connection might be closed
                break

async def send_initial_data(websocket: WebSocket, channel: str, db):
    """Send initial data when subscribing to a channel"""
    try:
        logger.info(f"Sending initial data for channel: {channel}")
        
        if channel == "products":
            await send_products(websocket, db)
        elif channel == "orders":
            await send_orders(websocket, {}, db)
        elif channel == "inventory":
            await send_inventory_status(websocket, db)
        elif channel == "customers":
            await send_customers(websocket, db)
        elif channel == "brands":
            await send_brands(websocket, db)
        elif channel == "categories":
            await send_categories(websocket, db)
        elif channel == "users":
            await handle_get_users(websocket, {}, db)
            
    except Exception as e:
        logger.error(f"Error sending initial data for {channel}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to load {channel} data"
        })