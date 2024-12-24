import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import CaseReviewRequest
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    try:
        settings = Settings()
        portfolio_service = PortfolioService(settings)
        
        try:
            req_body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)
        
        try:
            request = CaseReviewRequest(**req_body)
        except Exception as e:
            return handle_response(
                error=f"Invalid request format: {str(e)}", 
                status_code=400
            )
        
        result = await portfolio_service.generate_case_review(
            case_description=request.case_description,
            selected_capabilities=request.selected_capabilities
        )
        
        return handle_response(data=result.dict())
        
    except Exception as e:
        logging.error(f"Error generating review: {str(e)}")
        return handle_response(error=str(e), status_code=500)
