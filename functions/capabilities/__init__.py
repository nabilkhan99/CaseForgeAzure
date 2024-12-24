import azure.functions as func
import json
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.middleware import cors_middleware, handle_response

@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for capabilities.')
    
    try:
        # Initialize settings and service
        settings = Settings()
        portfolio_service = PortfolioService(settings)
        
        # Get capabilities
        capabilities = await portfolio_service.get_capabilities()
        
        return handle_response(data={"capabilities": capabilities})
        
    except Exception as e:
        logging.error(f"Error fetching capabilities: {str(e)}")
        return handle_response(error=str(e), status_code=500) 