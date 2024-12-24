import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import ImprovementRequest
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for review improvement.')
    
    try:
        # Initialize settings and service
        settings = Settings()
        portfolio_service = PortfolioService(settings)
        
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)
        
        # Validate request
        try:
            request = ImprovementRequest(**req_body)
        except Exception as e:
            return handle_response(
                error=f"Invalid request format: {str(e)}", 
                status_code=400
            )
        
        # Improve review
        result = await portfolio_service.improve_case_review(
            original_case=request.original_case,
            improvement_prompt=request.improvement_prompt,
            selected_capabilities=request.selected_capabilities
        )
        
        return handle_response(data=result.dict())
        
    except Exception as e:
        logging.error(f"Error improving review: {str(e)}")
        return handle_response(error=str(e), status_code=500)
