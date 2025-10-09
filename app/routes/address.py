from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, Query
import logging
from typing import List
from datetime import datetime

# from pydantic import BaseModel
from app.utils.auth import get_current_user
from db.db_manager import DatabaseManager, get_database
from schema.address import AddressCreate, AddressUpdate, AddressResponse,GeocodeRequest,ReverseGeocodeRequest,AddressSearchRequest
from app.utils.mongo import fix_mongo_types
from typing import List
import os
from dotenv import load_dotenv
import httpx
# from app.utils.address import get_fallback_address,get_fallback_coordinates,get_fallback_predictions

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_ADDRESSES_PER_USER = 5

load_dotenv()

OLA_API_KEY = os.getenv('OLA_KRUTRIM_API_KEY')
OLA_BASE_URL = os.getenv('OLA_BASE_URL')

@router.post("/", response_model=AddressResponse)
async def create_address(
    address_data: AddressCreate,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Create a new address for the user"""
    try:
        # Check address limit
        user_addresses_count = await db.count_documents("user_addresses", {
            "user_id": ObjectId(current_user.id)
        })
        
        if user_addresses_count >= MAX_ADDRESSES_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {MAX_ADDRESSES_PER_USER} addresses allowed. Please delete an existing address first."
            )
        
        # Check if user already has an address with this label
        existing_address = await db.find_one("user_addresses", {
            "user_id": ObjectId(current_user.id),
            "label": address_data.label
        })
        
        # Check if this is the first address for the user
        is_default = user_addresses_count == 0  # First address becomes default
        
        address_doc = address_data.dict()
        address_doc["user_id"] = ObjectId(current_user.id)
        address_doc["is_default"] = is_default
        address_doc["created_at"] = datetime.utcnow()
        address_doc["updated_at"] = datetime.utcnow()
        
        address_id = await db.insert_one("user_addresses", address_doc)
        
        # Get the created address
        created_address = await db.find_one("user_addresses", {"_id": ObjectId(address_id)})
        fixed_address = fix_mongo_types(created_address)
        
        logger.info(f"Address created successfully for user {current_user.email}")
        return AddressResponse(**fixed_address)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create address error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create address"
        )

@router.get("/my", response_model=List[AddressResponse])
async def get_user_addresses(
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Get all addresses for the user"""
    try:
        addresses = await db.find_many(
            "user_addresses",
            {"user_id": ObjectId(current_user.id)},
            sort=[("is_default", -1), ("created_at", -1)]  # Default first, then by creation date
        )
        
        fixed_addresses = [fix_mongo_types(address) for address in addresses]
        return [AddressResponse(**address) for address in fixed_addresses]
        
    except Exception as e:
        logger.error(f"Get addresses error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get addresses"
        )

@router.post("/{address_id}/set-default")
async def set_default_address(
    address_id: str,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Set an address as the default"""
    try:
        if not ObjectId.is_valid(address_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid address ID"
            )
        
        # Check if address belongs to user
        existing_address = await db.find_one("user_addresses", {
            "_id": ObjectId(address_id),
            "user_id": ObjectId(current_user.id)
        })
        
        if not existing_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        # Remove default from all user addresses
        await db.update_many(
            "user_addresses",
            {"user_id": ObjectId(current_user.id)},
            {"$set": {"is_default": False, "updated_at": datetime.utcnow()}}
        )
        
        # Set this address as default
        await db.update_one(
            "user_addresses",
            {"_id": ObjectId(address_id)},
            {"$set": {"is_default": True, "updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"Address {address_id} set as default")
        return {"message": "Default address updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set default address error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default address"
        )

@router.delete("/{address_id}")
async def delete_address(
    address_id: str,
    current_user=Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    """Delete an address"""
    try:
        if not ObjectId.is_valid(address_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid address ID"
            )
        
        # Check if address belongs to user
        existing_address = await db.find_one("user_addresses", {
            "_id": ObjectId(address_id),
            "user_id": ObjectId(current_user.id)
        })
        
        if not existing_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        # If deleting default address, make another address default
        if existing_address.get("is_default"):
            other_address = await db.find_one("user_addresses", {
                "user_id": ObjectId(current_user.id),
                "_id": {"$ne": ObjectId(address_id)}
            })
            
            if other_address:
                await db.update_one(
                    "user_addresses",
                    {"_id": other_address["_id"]},
                    {"$set": {"is_default": True, "updated_at": datetime.utcnow()}}
                )

        await db.delete_one("user_addresses", {"_id": ObjectId(address_id)})
        
        logger.info(f"Address {address_id} deleted successfully")
        return {"message": "Address deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete address error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete address"
        )

@router.post("/search-addresses")
async def search_addresses_proxy(request: AddressSearchRequest):
    """Proxy for Ola Maps address search"""
    try:
        if not request.query or len(request.query.strip()) < 3:
            return {"predictions": []}
        
        url = f"{OLA_BASE_URL}/autocomplete"
        params = {
            'input': request.query.strip(),
            'api_key': OLA_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                return {"predictions": data.get("predictions", [])}
            else:
                logger.error(f"Ola Maps search error: {response.status_code}")
                return {"predictions": []}
                
    except Exception as e:
        logger.error(f"Address search proxy error: {e}")
        return {"predictions": []}

@router.post("/geocode")
async def geocode_address(request: GeocodeRequest):
    """Proxy for Ola Maps geocoding"""
    try:
        url = f"{OLA_BASE_URL}/geocode"
        params = {
            'address': request.address,
            'api_key': OLA_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('geocodingResults') and len(data['geocodingResults']) > 0:
                    result = data['geocodingResults'][0]
                    location = result.get('geometry', {}).get('location', {})
                    
                    return {
                        'latitude': location.get('lat'),
                        'longitude': location.get('lng'),
                        'formatted_address': result.get('formatted_address'),
                        'place_id': result.get('place_id')
                    }
        
        raise HTTPException(status_code=404, detail="Address not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocode proxy error: {e}")
        raise HTTPException(status_code=500, detail="Geocoding failed")

@router.post("/reverse-geocode")
async def reverse_geocode_proxy(request: ReverseGeocodeRequest):
    """Proxy for Ola Maps reverse geocoding"""
    try:
        url = f"{OLA_BASE_URL}/reverse-geocode"
        params = {
            'latlng': f"{request.latitude},{request.longitude}",
            'api_key': OLA_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('results') and len(data['results']) > 0:
                    address_result = data['results'][0]
                    
                    return {
                        'formatted_address': address_result.get('formatted_address'),
                        'address_components': address_result.get('address_components', []),
                        'latitude': request.latitude,
                        'longitude': request.longitude
                    }
        
        raise HTTPException(status_code=404, detail="Address not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reverse geocode proxy error: {e}")
        raise HTTPException(status_code=500, detail="Reverse geocoding failed")
        
# @router.get("/search-addresses")
# async def search_addresses(query: str = Query(..., description="Address search query")):
#     """Search for addresses using Ola Maps API with fallback"""
#     try:
#         logger.info(f"🔍 Searching for: {query}")
        
#         if not query or not query.strip():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Query parameter is required"
#             )
        
#         # If no API key, use fallback immediately
#         if not OLA_KRUTRIM_API_KEY:
#             logger.warning("Ola Maps API key not configured, using fallback")
#             predictions = get_fallback_predictions(query)
#             return {"predictions": predictions}

#         # Try Ola Maps API
#         try:
#             async with httpx.AsyncClient(timeout=12.0) as client:
#                 response = await client.get(
#                     "https://api.olamaps.io/places/v1/autocomplete",
#                     params={
#                         "input": query,
#                         "api_key": OLA_KRUTRIM_API_KEY,
#                         "language": "en"
#                     },
#                     headers={
#                         "X-Request-Id": "backend-search"
#                     }
#                 )
                
#                 logger.info(f"Ola Maps API response status: {response.status_code}")
                
#                 if response.status_code == 200:
#                     data = response.json()
#                     logger.info(f"Ola Maps response for '{query}': {data.get('status')}")

#                     if data.get('status') == 'ok' and data.get('predictions'):
#                         predictions = []
#                         for pred in data.get("predictions", []):
#                             enhanced_pred = {
#                                 "place_id": pred.get("place_id", f"ola_{len(predictions)}"),
#                                 "description": pred.get("description", ""),
#                                 "structured_formatting": pred.get("structured_formatting", {
#                                     "main_text": pred.get("description", "").split(",")[0],
#                                     "secondary_text": ", ".join(pred.get("description", "").split(",")[1:])
#                                 }),
#                                 "types": pred.get("types", []),
#                                 "matched_substrings": pred.get("matched_substrings", [])
#                             }
#                             predictions.append(enhanced_pred)
                        
#                         if predictions:
#                             logger.info(f"✅ Returning {len(predictions)} Ola Maps predictions")
#                             return {"predictions": predictions}
                    
#                     # If Ola API returns no results, use fallback
#                     logger.info("Ola Maps returned no results, using fallback")
#                     predictions = get_fallback_predictions(query)
#                     return {"predictions": predictions}
#                 else:
#                     logger.warning(f"Ola Maps API returned non-200 status: {response.status_code}")
#                     # Use fallback on API error
#                     predictions = get_fallback_predictions(query)
#                     return {"predictions": predictions}

#         except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
#             logger.warning(f"Ola Maps API connection error: {e}")
#             # Use fallback on connection error
#             predictions = get_fallback_predictions(query)
#             return {"predictions": predictions}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Search error: {e}")
#         # Return fallback on any error
#         predictions = get_fallback_predictions(query)
#         return {"predictions": predictions}

# @router.post("/geocode")
# async def geocode_address(request: GeocodeRequest):
#     """Convert address to coordinates using Ola Maps API with fallback"""
#     try:
#         if not request.address or not request.address.strip():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Address is required"
#             )
        
#         logger.info(f"🗺️ Geocoding: {request.address}")
        
#         # If no API key, use fallback immediately
#         if not OLA_KRUTRIM_API_KEY:
#             logger.warning("Ola Maps API key not configured, using fallback")
#             return get_fallback_coordinates(request.address)

#         # Try Ola Maps API
#         try:
#             async with httpx.AsyncClient(timeout=12.0) as client:
#                 response = await client.get(
#                     "https://api.olamaps.io/places/v1/geocode",
#                     params={
#                         "address": request.address,
#                         "api_key": OLA_KRUTRIM_API_KEY,
#                         "language": "en"
#                     },
#                     headers={
#                         "X-Request-Id": "backend-geocode"
#                     }
#                 )
                
#                 logger.info(f"Ola Maps geocoding response status: {response.status_code}")
                
#                 if response.status_code == 200:
#                     data = response.json()
#                     logger.info(f"Ola Maps geocoding status: {data.get('status')}")
                    
#                     if data.get("status") == "ok" and data.get("geocodingResults"):
#                         result = data["geocodingResults"][0]
#                         location = result["geometry"]["location"]

#                         return {
#                             "latitude": location["lat"],
#                             "longitude": location["lng"],
#                             "formattedAddress": result["formatted_address"]
#                         }
#                     elif data.get("status") == "zero_results":
#                         logger.info(f"No results from Ola Maps for '{request.address}', trying fallback")
#                         return get_fallback_coordinates(request.address)
#                     else:
#                         logger.warning(f"Ola Maps returned status: {data.get('status')}")
#                         return get_fallback_coordinates(request.address)
#                 else:
#                     logger.warning(f"Ola Maps API error: {response.status_code}")
#                     return get_fallback_coordinates(request.address)

#         except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
#             logger.warning(f"Ola Maps API connection error: {e}")
#             return get_fallback_coordinates(request.address)
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Geocoding error: {e}")
#         return get_fallback_coordinates(request.address)

# @router.post("/reverse-geocode")
# async def reverse_geocode(request: ReverseGeocodeRequest):
#     """Convert coordinates to address using Ola Maps API with fallback"""
#     try:
#         logger.info(f"🔄 Reverse geocoding: {request.latitude}, {request.longitude}")
        
#         # If no API key, use fallback immediately
#         if not OLA_KRUTRIM_API_KEY:
#             logger.warning("Ola Maps API key not configured, using fallback")
#             return get_fallback_address(request.latitude, request.longitude)

#         # Try Ola Maps API
#         try:
#             async with httpx.AsyncClient(timeout=12.0) as client:
#                 response = await client.get(
#                     "https://api.olamaps.io/places/v1/reverse-geocode",
#                     params={
#                         "latlng": f"{request.latitude},{request.longitude}",
#                         "api_key": OLA_KRUTRIM_API_KEY,
#                         "language": "en"
#                     },
#                     headers={
#                         "X-Request-Id": "backend-reverse-geocode"
#                     }
#                 )
                
#                 logger.info(f"Ola Maps reverse geocoding response status: {response.status_code}")
                
#                 if response.status_code == 200:
#                     data = response.json()
#                     logger.info(f"Ola Maps reverse geocoding status: {data.get('status')}")
                    
#                     if data.get("status") == "ok" and data.get("reverseGeocodingResults"):
#                         result = data["reverseGeocodingResults"][0]
                        
#                         # Parse address components
#                         components = result.get("address_components", [])
#                         city = ""
#                         state = ""
#                         pincode = ""
                        
#                         for component in components:
#                             types = component.get("types", [])
#                             if "locality" in types:
#                                 city = component.get("long_name", "")
#                             elif "administrative_area_level_1" in types:
#                                 state = component.get("long_name", "")
#                             elif "postal_code" in types:
#                                 pincode = component.get("long_name", "")
                        
#                         return {
#                             "formattedAddress": result["formatted_address"],
#                             "city": city,
#                             "state": state,
#                             "pincode": pincode,
#                             "country": "India"
#                         }
#                     else:
#                         logger.info("No results from Ola Maps reverse geocoding, using fallback")
#                         return get_fallback_address(request.latitude, request.longitude)
#                 else:
#                     logger.warning(f"Ola Maps reverse geocoding error: {response.status_code}")
#                     return get_fallback_address(request.latitude, request.longitude)

#         except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
#             logger.warning(f"Ola Maps reverse geocoding connection error: {e}")
#             return get_fallback_address(request.latitude, request.longitude)
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Reverse geocoding error: {e}")
#         return get_fallback_address(request.latitude, request.longitude)