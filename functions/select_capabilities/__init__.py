import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import CapabilitySelectionRequest
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for capability selection.')
    
    try:
        settings = Settings()
        portfolio_service = PortfolioService(settings)
        
        try:
            req_body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)
        
        try:
            request = CapabilitySelectionRequest(**req_body)
        except Exception as e:
            return handle_response(
                error=f"Invalid request format: {str(e)}", 
                status_code=400
            )
        
        # Use AI to select capabilities
        selected_capabilities = await portfolio_service.select_capabilities_for_case(
            case_description=request.case_description
        )
        
        return handle_response(data={"selected_capabilities": selected_capabilities})
        
    except Exception as e:
        logging.error(f"Error selecting capabilities: {str(e)}")
        return handle_response(error=str(e), status_code=500)

