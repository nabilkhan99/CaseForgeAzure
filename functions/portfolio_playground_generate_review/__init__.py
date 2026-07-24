import azure.functions as func
import logging
from app.config import Settings
from app.services.portfolio_service import PortfolioService
from app.models import PlaygroundCaseReviewRequest
from app.middleware import cors_middleware, handle_response


@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a CCR using a per-request system-prompt override (playground only).
    Mirrors the former FastAPI POST /api/portfolio-playground/generate-review
    (consolidated off the Render dev-api onto Azure Functions). The override is
    applied to this request alone; it never changes the stored prompt."""
    logging.info('HTTP trigger: portfolio playground generate-review.')
    try:
        settings = Settings()
        portfolio_service = PortfolioService(settings)

        try:
            req_body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)

        try:
            request = PlaygroundCaseReviewRequest(**req_body)
        except Exception as e:
            return handle_response(error=f"Invalid request format: {str(e)}", status_code=400)

        result = await portfolio_service.generate_case_review(
            case_description=request.case_description,
            selected_capabilities=request.selected_capabilities,
            system_prompt_override=request.system_prompt,
            enforce_output_contract=True,
        )

        return handle_response(data=result.dict())

    except Exception as e:
        logging.error(f"Error generating playground review: {str(e)}")
        return handle_response(error=str(e), status_code=500)
