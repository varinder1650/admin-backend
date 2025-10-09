from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from typing import List
from datetime import datetime
from app.utils.auth import get_current_user
from db.db_manager import DatabaseManager, get_database
from schema.support import (
    SupportTicketCreate, SupportTicketResponse, SupportTicketStatus,
    ProductRequestCreate, ProductRequestResponse, ProductRequestStatus,
    TicketMessageCreate
)
from app.utils.mongo import fix_mongo_types

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/tickets", response_model=SupportTicketResponse)
async def create_support_ticket(
    ticket_data: SupportTicketCreate,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    try:
        logger.info(f"Creating support ticket for user {current_user.id}")
        
        ticket_doc = ticket_data.dict()
        ticket_doc["user_id"] = ObjectId(current_user.id)
        ticket_doc["user_name"] = current_user.name
        ticket_doc["user_email"] = current_user.email
        ticket_doc["status"] = SupportTicketStatus.OPEN
        ticket_doc["priority"] = ticket_data.priority if hasattr(ticket_data, 'priority') else "medium"
        ticket_doc["created_at"] = datetime.utcnow()
        ticket_doc["updated_at"] = datetime.utcnow()
        ticket_doc["messages"] = []  # Initialize empty messages array
        ticket_doc["assigned_to"] = None
        ticket_doc["admin_response"] = None
        
        # Convert order_id to ObjectId if provided
        if ticket_doc.get("order_id"):
            if ObjectId.is_valid(ticket_doc["order_id"]):
                ticket_doc["order_id"] = ObjectId(ticket_doc["order_id"])
            else:
                ticket_doc["order_id"] = None
        
        ticket_id = await db.insert_one("support_tickets", ticket_doc)
        
        # Get the created ticket
        created_ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        fixed_ticket = fix_mongo_types(created_ticket)
        
        logger.info(f"Support ticket created for user {current_user.email}: {ticket_data.subject}")
        
        return SupportTicketResponse(**fixed_ticket)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create support ticket error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support ticket"
        )

@router.get("/tickets", response_model=List[SupportTicketResponse])
async def get_user_tickets(
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Get all support tickets for the current user"""
    try:
        tickets = await db.find_many(
            "support_tickets",
            {"user_id": ObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        fixed_tickets = [fix_mongo_types(ticket) for ticket in tickets]
        return [SupportTicketResponse(**ticket) for ticket in fixed_tickets]
        
    except Exception as e:
        logger.error(f"Get user tickets error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get support tickets"
        )

@router.get("/tickets/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Get detailed information about a specific ticket including all messages"""
    try:
        logger.info(f"Fetching ticket detail for ticket {ticket_id}")
        
        # Validate ticket_id format
        if not ObjectId.is_valid(ticket_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID"
            )
        
        # Get ticket
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check if user owns this ticket
        if str(ticket["user_id"]) != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Format messages
        formatted_messages = []
        for msg in ticket.get("messages", []):
            formatted_message = {
                "_id": str(msg.get("_id", ObjectId())),
                "message": msg["message"],
                "sender_type": msg["sender_type"],
                "sender_name": msg["sender_name"],
                "sender_id": str(msg.get("sender_id", "")),
                "created_at": msg["created_at"],
                "attachments": msg.get("attachments", [])
            }
            formatted_messages.append(formatted_message)
        
        # Format ticket response
        ticket_response = {
            "_id": str(ticket["_id"]),
            "category": ticket["category"],
            "subject": ticket["subject"],
            "message": ticket["message"],
            "status": ticket["status"],
            "priority": ticket.get("priority", "medium"),
            "created_at": ticket["created_at"],
            "updated_at": ticket.get("updated_at", ticket["created_at"]),
            "user_id": str(ticket["user_id"]),
            "user_name": ticket.get("user_name", ""),
            "user_email": ticket.get("user_email", ""),
            "assigned_to": ticket.get("assigned_to"),
            "admin_response": ticket.get("admin_response"),
            "messages": formatted_messages,
            "order_id": str(ticket["order_id"]) if ticket.get("order_id") else None
        }
        
        logger.info(f"Ticket detail fetched successfully for ticket {ticket_id}")
        return ticket_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ticket detail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch ticket details"
        )

@router.post("/tickets/{ticket_id}/messages")
async def add_ticket_message(
    ticket_id: str,
    message_data: TicketMessageCreate,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Add a new message to an existing ticket"""
    try:
        logger.info(f"Adding message to ticket {ticket_id} from user {current_user.id}")
        
        # Validate ticket_id format
        if not ObjectId.is_valid(ticket_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID"
            )
        
        # Get ticket
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check if user owns this ticket
        if str(ticket["user_id"]) != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Check if ticket is closed
        if ticket["status"] == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add messages to closed tickets"
            )
        
        # Create new message
        new_message = {
            "_id": ObjectId(),
            "message": message_data.message.strip(),
            "sender_type": "user",
            "sender_name": current_user.name,
            "sender_id": current_user.id,
            "created_at": datetime.utcnow(),
            "attachments": []
        }
        
        # Add message to ticket and update status
        update_data = {
            "$push": {"messages": new_message},
            "$set": {
                "updated_at": datetime.utcnow(),
                # Reopen ticket if it was resolved and user sends new message
                "status": "open" if ticket["status"] == "resolved" else ticket["status"]
            }
        }
        
        await db.update_one(
            "support_tickets",
            {"_id": ObjectId(ticket_id)},
            update_data
        )
        
        logger.info(f"Message added to ticket {ticket_id} by user {current_user.id}")
        
        return {
            "success": True,
            "message": "Message added successfully",
            "ticket_message": {
                "_id": str(new_message["_id"]),
                "message": new_message["message"],
                "sender_type": new_message["sender_type"],
                "sender_name": new_message["sender_name"],
                "created_at": new_message["created_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding ticket message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add message"
        )

@router.patch("/tickets/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    status_data: dict,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Update ticket status (user can mark as resolved/closed)"""
    try:
        new_status = status_data.get("status")
        valid_user_statuses = ["resolved", "closed"]  # Users can only resolve or close
        
        if new_status not in valid_user_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Users can only mark tickets as resolved or closed."
            )
        
        # Validate ticket exists and user owns it
        ticket = await db.find_one("support_tickets", {"_id": ObjectId(ticket_id)})
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if str(ticket["user_id"]) != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update ticket status
        await db.update_one(
            "support_tickets",
            {"_id": ObjectId(ticket_id)},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"Ticket {ticket_id} status updated to {new_status} by user {current_user.id}")
        
        return {
            "success": True,
            "message": f"Ticket marked as {new_status}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ticket status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ticket status"
        )

# Keep your existing product request endpoints
@router.post("/product-requests", response_model=ProductRequestResponse)
async def create_product_request(
    request_data: ProductRequestCreate,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Create a new product request"""
    try:
        # Check if user already has a similar product request
        similar_request = await db.find_one("product_requests", {
            "user_id": ObjectId(current_user.id),
            "product_name": {"$regex": request_data.product_name, "$options": "i"},
            "status": {"$in": [ProductRequestStatus.PENDING, ProductRequestStatus.UNDER_REVIEW]}
        })
        
        if similar_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a pending request for a similar product"
            )
        
        request_doc = request_data.dict()
        request_doc["user_id"] = ObjectId(current_user.id)
        request_doc["user_name"] = current_user.name
        request_doc["user_email"] = current_user.email
        request_doc["status"] = ProductRequestStatus.PENDING
        request_doc["votes"] = 1  # User's own vote
        request_doc["created_at"] = datetime.utcnow()
        request_doc["updated_at"] = datetime.utcnow()
        
        request_id = await db.insert_one("product_requests", request_doc)
        
        # Get the created request
        created_request = await db.find_one("product_requests", {"_id": ObjectId(request_id)})
        fixed_request = fix_mongo_types(created_request)
        
        logger.info(f"Product request created for user {current_user.email}: {request_data.product_name}")
        
        return ProductRequestResponse(**fixed_request)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create product request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product request"
        )

@router.get("/tickets", response_model=List[SupportTicketResponse])
async def get_user_tickets(
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Get all support tickets for the current user with message counts"""
    try:
        tickets = await db.find_many(
            "support_tickets",
            {"user_id": ObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        # Enhance tickets with message counts and latest message info
        enhanced_tickets = []
        for ticket in tickets:
            fixed_ticket = fix_mongo_types(ticket)
            
            # Add message count
            messages = ticket.get("messages", [])
            fixed_ticket["message_count"] = len(messages)
            
            # Add latest admin response indicator
            latest_admin_message = None
            for msg in reversed(messages):
                if msg.get("sender_type") == "admin":
                    latest_admin_message = msg
                    break
            
            if latest_admin_message:
                fixed_ticket["has_new_admin_response"] = True
                fixed_ticket["latest_admin_response_at"] = latest_admin_message.get("created_at")
            else:
                fixed_ticket["has_new_admin_response"] = False
            
            enhanced_tickets.append(SupportTicketResponse(**fixed_ticket))
        
        return enhanced_tickets
        
    except Exception as e:
        logger.error(f"Get user tickets error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get support tickets"
        )

@router.get("/product-requests", response_model=List[ProductRequestResponse])
async def get_user_product_requests(
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Get all product requests for the current user"""
    try:
        requests = await db.find_many(
            "product_requests",
            {"user_id": ObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        fixed_requests = [fix_mongo_types(request) for request in requests]
        return [ProductRequestResponse(**request) for request in fixed_requests]
        
    except Exception as e:
        logger.error(f"Get user product requests error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get product requests"
        )

@router.post("/product-requests/{request_id}/vote")
async def vote_product_request(
    request_id: str,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Vote for a product request"""
    try:
        if not ObjectId.is_valid(request_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request ID"
            )
        
        # Check if request exists
        request_doc = await db.find_one("product_requests", {"_id": ObjectId(request_id)})
        if not request_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product request not found"
            )
        
        # Check if user already voted
        existing_vote = await db.find_one("product_request_votes", {
            "request_id": ObjectId(request_id),
            "user_id": ObjectId(current_user.id)
        })
        
        if existing_vote:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already voted for this request"
            )
        
        # Add vote
        await db.insert_one("product_request_votes", {
            "request_id": ObjectId(request_id),
            "user_id": ObjectId(current_user.id),
            "voted_at": datetime.utcnow()
        })
        
        # Update vote count
        await db.update_one(
            "product_requests",
            {"_id": ObjectId(request_id)},
            {
                "$inc": {"votes": 1},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        logger.info(f"User {current_user.email} voted for product request {request_id}")
        return {"message": "Vote added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vote product request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to vote for product request"
        )