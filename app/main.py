


# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
from .models import (
    CaseReviewRequest,
    CaseReviewResponse,
    PlaygroundCaseReviewRequest,
    ImprovementRequest,
    CapabilitiesResponse,
    ErrorResponse
)
from .services.portfolio_service import PortfolioService
from .config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GP Portfolio API",
    description="API for generating and managing GP portfolio case reviews",
    version="1.0.0"
)

# Load settings
settings = Settings()


def parse_cors_origins(value: str) -> List[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


# Configure CORS
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "https://fourteenfisherman.com",
    "https://www.fourteenfisherman.com",
    "https://case-forge-frontend-n5fd.vercel.app",
]
origins = default_origins + parse_cors_origins(settings.cors_allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=settings.cors_allowed_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to GP Portfolio API", "status": "running"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Dependency to get portfolio service
def get_portfolio_service():
    return PortfolioService(settings)

@app.post("/api/generate-review", response_model=CaseReviewResponse)
async def generate_review(
    request: CaseReviewRequest,
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    try:
        logger.info(f"Generating review for case with {len(request.selected_capabilities)} capabilities")
        result = await portfolio_service.generate_case_review(
            case_description=request.case_description,
            selected_capabilities=request.selected_capabilities
        )
        return result
    except Exception as e:
        logger.error(f"Error generating review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio-playground/prompt")
async def get_portfolio_playground_prompt():
    try:
        return {
            "system_prompt": settings.SYSTEM_PROMPT.strip(),
            "source": "CaseForgeAzure Settings.SYSTEM_PROMPT",
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio prompt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio-playground/generate-review", response_model=CaseReviewResponse)
async def generate_portfolio_playground_review(
    request: PlaygroundCaseReviewRequest,
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    try:
        logger.info("Generating playground review with prompt override")
        result = await portfolio_service.generate_case_review(
            case_description=request.case_description,
            selected_capabilities=request.selected_capabilities,
            system_prompt_override=request.system_prompt,
            enforce_output_contract=True,
        )
        return result
    except Exception as e:
        logger.error(f"Error generating playground review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/improve-review", response_model=CaseReviewResponse)
async def improve_review(
    request: ImprovementRequest,
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    try:
        logger.info("Improving existing review")
        result = await portfolio_service.improve_case_review(
            original_case=request.original_case,
            improvement_prompt=request.improvement_prompt,
            selected_capabilities=request.selected_capabilities
        )
        return result
    except Exception as e:
        logger.error(f"Error improving review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    try:
        logger.info("Fetching capabilities")
        capabilities = await portfolio_service.get_capabilities()
        logger.info(f"Returning capabilities: {capabilities}")
        return {"capabilities": capabilities}
    except Exception as e:
        logger.error(f"Error fetching capabilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=True,
            message=str(exc.detail)
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=True,
            message="An unexpected error occurred"
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
