from fastapi import WebSocket
from bson import ObjectId
from datetime import datetime
from admin.utils.serialize import serialize_document
import logging

logger = logging.getLogger(__name__)

async def get_tickets(websocket: WebSocket, filters: dict, db):
    try:
        # Build query based on filters - exclude "all" values
        query = {}
        
        if filters.get("status") and filters["status"] != "all":
            query["status"] = filters["status"]
        
        if filters.get("priority") and filters["priority"] != "all":
            query["priority"] = filters["priority"]
        
        if filters.get("category") and filters["category"] != "all":
            query["category"] = filters["category"]
        
        logger.info(f"Fetching tickets with query: {query}")
        
        # Get tickets
        tickets = await db.find_many(
            "support_tickets", 
            query, 
            sort=[("created_at", -1)]
        )
        
        logger.info(f"Found {len(tickets)} tickets")
        
        # Process each ticket and handle datetime serialization
        enriched_tickets = []
        for ticket in tickets:
            try:
                # Get user info for this ticket
                user_info = None
                if ticket.get("user_id"):
                    user_info = await db.find_one("users", {"_id": ticket["user_id"]})
                
                # Manual serialization to handle datetime objects
                serialized_ticket = {
                    "_id": str(ticket["_id"]),
                    "id": str(ticket["_id"]),  # Add id field for compatibility
                    "subject": ticket.get("subject", ""),
                    "category": ticket.get("category", "other"),
                    "priority": ticket.get("priority", "medium"),
                    "status": ticket.get("status", "open"),
                    "message": ticket.get("message", ""),
                    "created_at": ticket["created_at"].isoformat() if ticket.get("created_at") else None,
                    "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
                    "admin_response": ticket.get("admin_response"),
                    "responded_at": ticket.get("responded_at").isoformat() if ticket.get("responded_at") else None,
                    "order_id": str(ticket["order_id"]) if ticket.get("order_id") else None,
                }
                # Add user information
                if user_info:
                    serialized_ticket["user_name"] = user_info.get("name", "Unknown")
                    serialized_ticket["user_email"] = user_info.get("email", "Unknown")
                    serialized_ticket["user_phone"] = user_info.get("phone", "Not provided")
                else:
                    # Fallback to ticket's stored user info
                    serialized_ticket["user_name"] = ticket.get("user_name", "Unknown")
                    serialized_ticket["user_email"] = ticket.get("user_email", "Unknown")
                    serialized_ticket["user_phone"] = "Not provided"
                # print(serialized_ticket)
                # Add message count and latest message info
                messages = ticket.get("messages", [])
                serialized_ticket["message_count"] = len(messages)
                
                formatted_messages = []
                for msg in messages:
                    try:
                        formatted_message = {
                            "_id": str(msg.get("_id", ObjectId())),
                            "message": msg.get("message", ""),
                            "sender_type": msg.get("sender_type", "user"),
                            "sender_name": msg.get("sender_name", "Unknown"),
                            "sender_id": str(msg.get("sender_id", "")),
                            "created_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
                            "attachments": msg.get("attachments", [])
                        }
                        formatted_messages.append(formatted_message)
                    except Exception as msg_error:
                        logger.error(f"Error formatting message: {msg_error}")
                        continue
                
                # Include ALL messages in the ticket data
                serialized_ticket["messages"] = formatted_messages
                
                # Also include latest message info for quick reference
                if formatted_messages:
                    latest_message = formatted_messages[-1]
                    serialized_ticket["latest_message"] = {
                        "message": latest_message["message"],
                        "sender_type": latest_message["sender_type"],
                        "sender_name": latest_message["sender_name"],
                        "created_at": latest_message["created_at"]
                    }
                else:
                    serialized_ticket["latest_message"] = None
                
                # Add flags for admin panel UI
                has_unread_user_messages = any(
                    msg["sender_type"] == "user" 
                    for msg in formatted_messages 
                    if msg.get("created_at") and ticket.get("responded_at") and 
                    msg["created_at"] > ticket.get("responded_at").isoformat()
                )
                serialized_ticket["has_unread_user_messages"] = has_unread_user_messages
                
                enriched_tickets.append(serialized_ticket)
                # print(serialized_ticket)
            except Exception as ticket_error:
                logger.error(f"Error processing ticket {ticket.get('_id')}: {ticket_error}")
                # Include basic ticket info even if enrichment fails
                try:
                    basic_ticket = {
                        "_id": str(ticket["_id"]),
                        "id": str(ticket["_id"]),
                        "subject": ticket.get("subject", "Unknown"),
                        "category": ticket.get("category", "other"),
                        "priority": ticket.get("priority", "medium"),
                        "status": ticket.get("status", "open"),
                        "message": ticket.get("message", ""),
                        "user_name": ticket.get("user_name", "Unknown"),
                        "user_email": ticket.get("user_email", "Unknown"),
                        "user_phone": "Not provided",
                        "message_count": 0,
                        "created_at": ticket["created_at"].isoformat() if ticket.get("created_at") else None,
                        "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
                    }
                    enriched_tickets.append(basic_ticket)
                except Exception as basic_error:
                    logger.error(f"Failed to create basic ticket info: {basic_error}")
                    continue

        logger.info(f"Successfully processed {len(enriched_tickets)} tickets")

        await websocket.send_json({
            "type": "help_tickets_data",
            "tickets": enriched_tickets,
            "total_count": len(enriched_tickets)
        })
        
    except Exception as e:
        logger.error(f"Error getting tickets: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to fetch tickets: {str(e)}"
        })

async def get_ticket_detail(websocket: WebSocket, data: dict, db):
    """Get detailed ticket information with full message history"""
    try:
        ticket_id = data.get("ticket_id")
        
        if not ticket_id:
            await websocket.send_json({
                "type": "error",
                "message": "Ticket ID is required"
            })
            return
        
        if not ObjectId.is_valid(ticket_id):
            await websocket.send_json({
                "type": "error",
                "message": "Invalid ticket ID format"
            })
            return
        
        logger.info(f"Fetching ticket detail for {ticket_id}")
        
        # Get ticket
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            await websocket.send_json({
                "type": "error", 
                "message": "Ticket not found"
            })
            return
        
        # Get user information
        user_info = None
        if ticket.get("user_id"):
            user_info = await db.find_one("users", {"_id": ticket["user_id"]})
        
        # Manual serialization with proper datetime handling
        serialized_ticket = {
            "_id": str(ticket["_id"]),
            "id": str(ticket["_id"]),
            "subject": ticket.get("subject", ""),
            "category": ticket.get("category", "other"),
            "priority": ticket.get("priority", "medium"),
            "status": ticket.get("status", "open"),
            "message": ticket.get("message", ""),
            "created_at": ticket["created_at"].isoformat() if ticket.get("created_at") else None,
            "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
            "admin_response": ticket.get("admin_response"),
            "responded_at": ticket.get("responded_at").isoformat() if ticket.get("responded_at") else None,
            "order_id": str(ticket["order_id"]) if ticket.get("order_id") else None,
        }
        
        # Add user information
        if user_info:
            serialized_ticket["user_info"] = {
                "name": user_info.get("name", "Unknown"),
                "email": user_info.get("email", "Unknown"),
                "phone": user_info.get("phone", "Not provided"),
                "role": user_info.get("role", "user"),
                "created_at": user_info.get("created_at").isoformat() if user_info.get("created_at") else None
            }
        else:
            # Use ticket's stored user info as fallback
            serialized_ticket["user_info"] = {
                "name": ticket.get("user_name", "Unknown"),
                "email": ticket.get("user_email", "Unknown"),
                "phone": "Not provided",
                "role": "user",
                "created_at": None
            }
        
        # FIXED: Format ALL messages with proper datetime serialization
        formatted_messages = []
        messages = ticket.get("messages", [])
        
        for msg in messages:
            try:
                formatted_message = {
                    "_id": str(msg.get("_id", ObjectId())),
                    "message": msg.get("message", ""),
                    "sender_type": msg.get("sender_type", "user"),
                    "sender_name": msg.get("sender_name", "Unknown"),
                    "sender_id": str(msg.get("sender_id", "")),
                    "created_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
                    "attachments": msg.get("attachments", [])
                }
                formatted_messages.append(formatted_message)
            except Exception as msg_error:
                logger.error(f"Error formatting message {msg.get('_id')}: {msg_error}")
                # Include basic message info even if datetime conversion fails
                try:
                    basic_message = {
                        "_id": str(msg.get("_id", ObjectId())),
                        "message": msg.get("message", ""),
                        "sender_type": msg.get("sender_type", "user"),
                        "sender_name": msg.get("sender_name", "Unknown"),
                        "sender_id": str(msg.get("sender_id", "")),
                        "created_at": None,  # Set to None if conversion fails
                        "attachments": []
                    }
                    formatted_messages.append(basic_message)
                except:
                    continue  # Skip this message if it can't be processed at all
        
        serialized_ticket["messages"] = formatted_messages
        
        logger.info(f"Ticket detail prepared with {len(formatted_messages)} messages")
        
        await websocket.send_json({
            "type": "ticket_detail_data",
            "ticket": serialized_ticket
        })
        
    except Exception as e:
        logger.error(f"Error getting ticket detail: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to fetch ticket detail: {str(e)}"
        })

async def respond_to_ticket(websocket: WebSocket, data: dict, db):
    """Admin responds to a ticket"""
    try:
        ticket_id = data.get("ticket_id")
        response_message = data.get("response", "").strip()
        new_status = data.get("status", "in_progress")
        
        if not ticket_id or not response_message:
            await websocket.send_json({
                "type": "error",
                "message": "Ticket ID and response are required"
            })
            return
        
        if not ObjectId.is_valid(ticket_id):
            await websocket.send_json({
                "type": "error", 
                "message": "Invalid ticket ID"
            })
            return
        
        logger.info(f"Admin responding to ticket {ticket_id}")
        
        # Get ticket
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            await websocket.send_json({
                "type": "error",
                "message": "Ticket not found"
            })
            return
        
        # Create admin response message
        admin_message = {
            "_id": ObjectId(),
            "message": response_message,
            "sender_type": "admin",
            "sender_name": "Support Team",
            "sender_id": "admin_001",
            "created_at": datetime.utcnow(),
            "attachments": []
        }
        
        # Update ticket with response
        current_messages = ticket.get("messages", [])
        current_messages.append(admin_message)
        
        update_data = {
            "messages": current_messages,
            "admin_response": response_message,
            "status": new_status,
            "updated_at": datetime.utcnow(),
            "responded_at": datetime.utcnow()
        }
        
        await db.update_one(
            "support_tickets",
            {"_id": ObjectId(ticket_id)},
            update_data
        )
        
        logger.info(f"Admin responded to ticket {ticket_id}")
        
        # Send success response with properly serialized message
        response_data = {
            "type": "ticket_updated",
            "message": "Response sent successfully",
            "ticket_id": ticket_id,
            "new_message": {
                "_id": str(admin_message["_id"]),
                "message": admin_message["message"],
                "sender_type": admin_message["sender_type"],
                "sender_name": admin_message["sender_name"],
                "created_at": admin_message["created_at"].isoformat()  # FIXED: Convert datetime
            }
        }
        
        await websocket.send_json(response_data)
        
    except Exception as e:
        logger.error(f"Error responding to ticket: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to send response: {str(e)}"
        })

async def update_ticket_status(websocket: WebSocket, data: dict, db):
    """Update ticket status"""
    try:
        ticket_id = data.get("ticket_id")
        new_status = data.get("status")
        admin_note = data.get("admin_note", "")
        
        valid_statuses = ["open", "in_progress", "resolved", "closed"]
        
        if not ticket_id or not new_status:
            await websocket.send_json({
                "type": "error",
                "message": "Ticket ID and status are required"
            })
            return
        
        if new_status not in valid_statuses:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid status. Valid options: {', '.join(valid_statuses)}"
            })
            return
        
        if not ObjectId.is_valid(ticket_id):
            await websocket.send_json({
                "type": "error",
                "message": "Invalid ticket ID format"
            })
            return
        
        logger.info(f"Updating ticket {ticket_id} status to {new_status}")
        
        # Get current ticket
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            await websocket.send_json({
                "type": "error",
                "message": "Ticket not found"
            })
            return
        
        # Update ticket status
        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        
        # Add system message if admin note is provided
        if admin_note:
            current_messages = ticket.get("messages", [])
            system_message = {
                "_id": ObjectId(),
                "message": f"Status changed to '{new_status}'. Note: {admin_note}",
                "sender_type": "system",
                "sender_name": "System",
                "sender_id": "system",
                "created_at": datetime.utcnow(),
                "attachments": []
            }
            current_messages.append(system_message)
            update_data["messages"] = current_messages
        
        await db.update_one(
            "support_tickets",
            {"_id": ObjectId(ticket_id)},
            update_data
        )
        
        logger.info(f"Ticket {ticket_id} status updated to {new_status}")
        
        await websocket.send_json({
            "type": "ticket_updated",
            "message": f"Ticket status updated to {new_status}",
            "ticket_id": ticket_id
        })
        
    except Exception as e:
        logger.error(f"Error updating ticket status: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to update status: {str(e)}"
        })

async def get_ticket_stats(websocket: WebSocket, data: dict, db):
    """Get ticket statistics for dashboard"""
    try:
        logger.info("Fetching ticket statistics")
        
        # Get all tickets to calculate stats
        all_tickets = await db.find_many("support_tickets", {})
        
        # Calculate status breakdown
        status_breakdown = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
        today_count = 0
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for ticket in all_tickets:
            status = ticket.get("status", "open")
            if status in status_breakdown:
                status_breakdown[status] += 1
            
            # Count today's tickets
            created_at = ticket.get("created_at")
            if created_at and created_at >= today_start:
                today_count += 1
        
        stats = {
            "total_tickets": len(all_tickets),
            "today_tickets": today_count,
            "status_breakdown": status_breakdown
        }
        
        await websocket.send_json({
            "type": "ticket_stats_data",
            "stats": stats
        })
        
        logger.info(f"Sent ticket stats: {stats}")
        
    except Exception as e:
        logger.error(f"Error getting ticket stats: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to get stats: {str(e)}"
        })