from fastapi import FastAPI
from app.middleware.setup import setup_middleware
from db.config import settings
from app.routes import categories, products, orders, auth, cart, brands, settings as settings_route,address,support,delivery,coupons
from datetime import datetime

def create_customer_app() -> FastAPI:
    app = FastAPI(
        title="SmartBag",
        version='1.0.0',
        description="QuickCom app"
    )

    setup_middleware(app)

    # Include all routes with proper prefixes
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(products.router, prefix="/products", tags=["Products"])
    app.include_router(categories.router, prefix="/categories", tags=["Categories"])
    app.include_router(brands.router, prefix="/brands", tags=["Brands"]) 
    app.include_router(orders.router, prefix="/orders", tags=["Orders"])
    app.include_router(cart.router, prefix="/cart", tags=["Cart"])
    app.include_router(settings_route.router, prefix="/settings", tags=["Settings"])  
    app.include_router(address.router, prefix="/address", tags=["Address"])
    app.include_router(support.router, prefix = "/support", tags=["Support"])
    app.include_router(delivery.router, prefix="/delivery", tags=["Delivery"])
    app.include_router(coupons.router, prefix = "/promocodes", tags=["Coupons"])

    @app.get("/")
    async def root():
        return {"message": "SmartBag API is running!", "status": "healthy"}
    
    # Add health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }

    return app