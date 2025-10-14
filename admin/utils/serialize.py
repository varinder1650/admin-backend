from datetime import datetime
from bson import ObjectId

def serialize_document(doc):
    """Recursively convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None

    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    if isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    if isinstance(doc, dict):
        return {key: serialize_document(value) for key, value in doc.items()}

    # Leave other types unchanged
    return doc
