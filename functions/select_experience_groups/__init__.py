import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import ExperienceGroupRequest
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for experience group selection.')
    
    try:
        settings = Settings()
        portfolio_service = PortfolioService(settings)
        
        try:
            req_body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)
        
        try:
            request = ExperienceGroupRequest(**req_body)
        except Exception as e:
            return handle_response(
                error=f"Invalid request format: {str(e)}", 
                status_code=400
            )
        
        # Use AI to select experience groups
        experience_groups = await portfolio_service.select_experience_groups(
            case_description=request.case_description
        )
        
        return handle_response(data={"experience_groups": experience_groups})
        
    except Exception as e:
        logging.error(f"Error selecting experience groups: {str(e)}")
        return handle_response(error=str(e), status_code=500)

