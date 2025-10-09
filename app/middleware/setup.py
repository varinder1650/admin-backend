from fastapi import FastAPI, Request, HTTPException
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uuid
import time
from datetime import datetime
from fastapi.responses import JSONResponse
import traceback

logger = logging.getLogger(__name__)

def setup_middleware(app: FastAPI):
    #security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )

    #CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins = ["*"],
        allow_credentials = True,
        allow_methods = ["*"],
        allow_headers = ["*"]
    )

    #compression middleware
    app.add_middleware(GZipMiddleware,minimum_size = 1000)

    #request ID middleware fro tracking
    @app.middleware("http")
    async def error_handling_middleware(request:Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            raise
        except Exception as e:
            request_id = getattr(request.state, 'request_id', 'unknown')
            logger.error(f"[{request_id}] unhandled exception: {type(e).__name__}")
            logger.error(f"[{request_id}] Error details: {str(e)}")
            logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    # Request Logging Middleware
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Log all requests and responses"""
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Get request details
        start_time = time.time()
        client = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
        
        # Log request
        logger.info(
            f"[{request_id}] Started {request.method} {request.url.path} "
            f"from {client}"
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"[{request_id}] Completed {request.method} {request.url.path} "
            f"with status {response.status_code} in {duration:.3f}s"
        )
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        
        return response

    # Database Middleware
    @app.middleware("http")
    async def database_middleware(request: Request, call_next):
        """Ensure database is available for each request"""
        # Add database to request state if needed
        if hasattr(app.state, 'db'):
            request.state.db = app.state.db
        
        response = await call_next(request)
        return response