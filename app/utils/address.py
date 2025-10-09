import logging

logger = logging.getLogger(__name__)

# Define CITIES dictionary (it was missing in your code)
CITIES = {
    'mumbai': {'latitude': 19.0760, 'longitude': 72.8777, 'state': 'Maharashtra'},
    'delhi': {'latitude': 28.7041, 'longitude': 77.1025, 'state': 'Delhi'},
    'bangalore': {'latitude': 12.9716, 'longitude': 77.5946, 'state': 'Karnataka'},
    'bengaluru': {'latitude': 12.9716, 'longitude': 77.5946, 'state': 'Karnataka'},
    'chennai': {'latitude': 13.0827, 'longitude': 80.2707, 'state': 'Tamil Nadu'},
    'kolkata': {'latitude': 22.5726, 'longitude': 88.3639, 'state': 'West Bengal'},
    'pune': {'latitude': 18.5204, 'longitude': 73.8567, 'state': 'Maharashtra'},
    'hyderabad': {'latitude': 17.3850, 'longitude': 78.4867, 'state': 'Telangana'},
    'ahmedabad': {'latitude': 23.0225, 'longitude': 72.5714, 'state': 'Gujarat'},
    'jaipur': {'latitude': 26.9124, 'longitude': 75.7873, 'state': 'Rajasthan'},
    'lucknow': {'latitude': 26.8467, 'longitude': 80.9462, 'state': 'Uttar Pradesh'},
    'kanpur': {'latitude': 26.4499, 'longitude': 80.3319, 'state': 'Uttar Pradesh'},
    'nagpur': {'latitude': 21.1458, 'longitude': 79.0882, 'state': 'Maharashtra'},
    'indore': {'latitude': 22.7196, 'longitude': 75.8577, 'state': 'Madhya Pradesh'},
    'thane': {'latitude': 19.2183, 'longitude': 72.9781, 'state': 'Maharashtra'},
    'bhopal': {'latitude': 23.2599, 'longitude': 77.4126, 'state': 'Madhya Pradesh'},
    'visakhapatnam': {'latitude': 17.6868, 'longitude': 83.2185, 'state': 'Andhra Pradesh'},
    'patna': {'latitude': 25.5941, 'longitude': 85.1376, 'state': 'Bihar'},
    'vadodara': {'latitude': 22.3072, 'longitude': 73.1812, 'state': 'Gujarat'},
    'ghaziabad': {'latitude': 28.6692, 'longitude': 77.4538, 'state': 'Uttar Pradesh'},
    'ludhiana': {'latitude': 30.9010, 'longitude': 75.8573, 'state': 'Punjab'},
    'agra': {'latitude': 27.1767, 'longitude': 78.0081, 'state': 'Uttar Pradesh'},
    'nashik': {'latitude': 19.9975, 'longitude': 73.7898, 'state': 'Maharashtra'},
    'faridabad': {'latitude': 28.4089, 'longitude': 77.3178, 'state': 'Haryana'},
    'meerut': {'latitude': 28.9845, 'longitude': 77.7064, 'state': 'Uttar Pradesh'},
    'rajkot': {'latitude': 22.3039, 'longitude': 70.8022, 'state': 'Gujarat'},
    'kalyan': {'latitude': 19.2437, 'longitude': 73.1355, 'state': 'Maharashtra'},
    'vasai': {'latitude': 19.4883, 'longitude': 72.8056, 'state': 'Maharashtra'},
    'varanasi': {'latitude': 25.3176, 'longitude': 82.9739, 'state': 'Uttar Pradesh'},
    'san francisco': {'latitude': 37.7749, 'longitude': -122.4194, 'state': 'California'},
}

def get_fallback_address(latitude: float, longitude: float):
    """Get fallback address from nearest city"""
    # Find nearest city
    min_distance = float('inf')
    nearest_city = None
    nearest_data = None
    
    for city, data in CITIES.items():
        distance = ((latitude - data['latitude']) ** 2 + 
                   (longitude - data['longitude']) ** 2) ** 0.5
        
        if distance < min_distance:
            min_distance = distance
            nearest_city = city
            nearest_data = data
    
    if nearest_city and min_distance < 1.0:  # Within ~111km
        formatted_address = f"Near {nearest_city.title()}, {nearest_data['state']}, India"
        logger.info(f"✅ Found nearest city: {nearest_city}")
        return {
            "formattedAddress": formatted_address,
            "city": nearest_city.title(),
            "state": nearest_data['state'],
            "country": "India"
        }
    else:
        formatted_address = f"Location at {latitude:.4f}, {longitude:.4f}"
        logger.info(f"❌ No nearby city found")
        return {
            "formattedAddress": formatted_address,
            "city": "Unknown",
            "state": "Unknown",
            "country": "India"
        }


def get_fallback_predictions(query: str):
    """Generate fallback predictions when Ola API fails"""
    query_lower = query.lower()
    predictions = []
    
    # Search through cities for matches
    for city, data in CITIES.items():
        if query_lower in city or city in query_lower:
            predictions.append({
                "place_id": f"city_{city}",
                "description": f"{city.title()}, {data['state']}, India",
                "structured_formatting": {
                    "main_text": city.title(),
                    "secondary_text": f"{data['state']}, India"
                }
            })
    
    # If no exact matches, try partial matches
    if not predictions:
        for city, data in CITIES.items():
            if any(part in city for part in query_lower.split() if len(part) > 2):
                predictions.append({
                    "place_id": f"partial_{city}",
                    "description": f"{city.title()}, {data['state']}, India (Similar)",
                    "structured_formatting": {
                        "main_text": city.title(),
                        "secondary_text": f"{data['state']}, India - Similar match"
                    }
                })
    
    # Always add manual entry
    predictions.append({
        "place_id": "manual",
        "description": query,
        "structured_formatting": {
            "main_text": query,
            "secondary_text": "Enter this address manually"
        }
    })
    
    return predictions[:6]


def get_fallback_coordinates(address: str):
    """Get fallback coordinates from local city database"""
    address_lower = address.lower()
    
    # Find city in address
    for city, data in CITIES.items():
        if city in address_lower:
            logger.info(f"✅ Found fallback coordinates for {city}")
            return {
                "latitude": data['latitude'],
                "longitude": data['longitude'],
                "formattedAddress": address,
                "note": f"Approximate coordinates for {city.title()}"
            }
    
    logger.info(f"❌ No coordinates found for: {address}")
    return {
        "latitude": None,
        "longitude": None,
        "formattedAddress": address,
        "note": "No coordinates available"
    }