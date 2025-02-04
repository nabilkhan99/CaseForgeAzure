import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import SectionImprovementRequest
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for section improvement.')
    
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
            request = SectionImprovementRequest(**req_body)
        except Exception as e:
            return handle_response(
                error=f"Invalid request format: {str(e)}", 
                status_code=400
            )
        
        # Improve section
        result = await portfolio_service.improve_section(
            section_type=request.section_type,
            section_content=request.section_content,
            improvement_prompt=request.improvement_prompt,
            capability_name=request.capability_name
        )
        
        return handle_response(data={"improved_content": result})
        
    except Exception as e:
        logging.error(f"Error improving section: {str(e)}")
        return handle_response(error=str(e), status_code=500) 