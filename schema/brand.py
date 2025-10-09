from pydantic import BaseModel,Field
from typing import Optional
from datetime import datetime

class BrandBase(BaseModel):
    name: str
    description: Optional[str] = None
    logo: Optional[str] = None

class BrandCreate(BrandBase):
    pass

class BrandResponse(BrandBase):
    id: str = Field(..., alias="_id")
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }