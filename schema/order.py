from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
from schema.products import ProductResponse


class OrderItem(BaseModel):
    product: str  # product id
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class OrderItemResponse(BaseModel):
    product: str
    quantity: int
    price: float


class OrderItemEnhancedResponse(BaseModel):
    product: str
    quantity: int
    price: float
    product_name: Optional[str] = None  # Add product name field
    product_image: Optional[List] = None  # Add product images field


class DeliveryAddress(BaseModel):
    address: str
    city: str
    state: str
    pincode: str


class StatusChange(BaseModel):
    status: str
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str


class UserInfo(BaseModel):
    name: str
    email: str
    phone: str


class OrderBase(BaseModel):
    user: str
    items: List[OrderItem]
    delivery_address: DeliveryAddress
    payment_method: str = "cod"
    subtotal: float = Field(..., gt=0)
    tax: float = Field(default=0, ge=0)
    delivery_charge: float = Field(default=0, ge=0)
    app_fee: float = Field(default=0, ge=0)
    total_amount: float = Field(..., gt=0)
    payment_status: str = "pending"
    order_status: str = "pending"
    status_change_history: List[StatusChange] = []
    delivery_partner: Optional[str] = None


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    order_status: Optional[str] = None
    payment_status: Optional[str] = None
    status_change_history: Optional[List[StatusChange]] = None
    delivery_partner: Optional[str] = None


class OrderInDB(OrderBase):
    pass


class OrderResponse(BaseModel):
    id: str = Field(None, alias="_id")
    user: str
    user_info: Optional[UserInfo] = None
    items: List[OrderItemResponse]   # product is just ID
    delivery_address: DeliveryAddress
    payment_method: str = "cod"
    subtotal: float
    tax: float = 0
    delivery_charge: float = 0
    app_fee: float = 0
    total_amount: float
    payment_status: str = "pending"
    order_status: str = "pending"
    status_change_history: List[StatusChange] = []
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    delivery_partner: Optional[str] = None
    delivery_partner_info: Optional[UserInfo] = None


class OrderResponseEnhanced(BaseModel):
    id: str = Field(None, alias="_id")
    user: str
    user_info: Optional[UserInfo] = None
    items: List[OrderItemEnhancedResponse]  # Now includes product_name
    delivery_address: DeliveryAddress
    payment_method: str = "cod"
    subtotal: float
    tax: float = 0
    delivery_charge: float = 0
    app_fee: float = 0
    total_amount: float
    payment_status: str = "pending"
    order_status: str = "pending"
    status_change_history: List[StatusChange] = []
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    delivery_partner: Optional[str] = None
    delivery_partner_info: Optional[UserInfo] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }