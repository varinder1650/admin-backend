def validate_and_clean_keywords(keywords: list) -> list:
    """Validate and clean user-provided keywords"""
    cleaned = []
    
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
            
        # Clean the keyword
        keyword = keyword.strip().lower()
        
        # Skip empty or too short keywords
        if len(keyword) < 2:
            continue
            
        # Remove special characters but keep spaces for multi-word keywords
        keyword = ''.join(c for c in keyword if c.isalnum() or c.isspace())
        
        # Limit keyword length
        if len(keyword) > 50:
            keyword = keyword[:50]
            
        if keyword and keyword not in cleaned:
            cleaned.append(keyword)
    
    # Limit total number of keywords
    return cleaned[:30]  # Maximum 30 keywords per product

def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from product name"""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')