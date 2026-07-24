import azure.functions as func
import logging
from app.config import Settings
from app.middleware import cors_middleware, handle_response


@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    """Return the current portfolio system prompt so the playground can load it
    for editing. Mirrors the former FastAPI GET /api/portfolio-playground/prompt
    (consolidated off the Render dev-api onto Azure Functions)."""
    logging.info('HTTP trigger: portfolio playground prompt.')
    try:
        settings = Settings()
        return handle_response(data={
            "system_prompt": settings.SYSTEM_PROMPT.strip(),
            "source": "CaseForgeAzure Settings.SYSTEM_PROMPT",
        })
    except Exception as e:
        logging.error(f"Error fetching portfolio prompt: {str(e)}")
        return handle_response(error=str(e), status_code=500)
