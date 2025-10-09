from typing import Optional,List
from pydantic import BaseModel, Field

class Category(BaseModel):
    name:str
    image: str = None

class CategoryResponse(Category):
    id: str = Field(..., alias="_id")
    
    class Config:
        populate_by_name = True