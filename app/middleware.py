
from typing import Callable
import azure.functions as func
import json

def cors_middleware(func_handler: Callable) -> Callable:
    async def wrapper(req: func.HttpRequest) -> func.HttpResponse:
        # Handle OPTIONS requests for CORS
        if req.method == "OPTIONS":
            response = func.HttpResponse(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Max-Age": "86400",
                }
            )
            return response

        # Call the actual function handler
        response = await func_handler(req)
        
        # Add CORS headers to response
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "GET, POST, OPTIONS"
        response.headers['Access-Control-Allow-Headers'] = "Content-Type,Authorization"
        
        return response
    
    return wrapper

def handle_response(data: dict = None, error: str = None, status_code: int = 200) -> func.HttpResponse:
    """Helper function to create consistent HTTP responses"""
    if error:
        response_data = {"error": error}
        if status_code < 400:
            status_code = 500
    else:
        response_data = data or {}
    
    return func.HttpResponse(
        json.dumps(response_data),
        mimetype="application/json",
        status_code=status_code
    ) 