"""HTTP trigger: build a cross-case trend report for one candidate.

POST /api/generate-trend  body: { "candidateId": "<uuid>" }
Guarded by the same shared secret as marking. Source: Build Package Section 13.
"""
import logging

import azure.functions as func
from openai import AsyncAzureOpenAI

from app.config import Settings
from app.middleware import cors_middleware, handle_response
from app.services.marking_service import make_azure_model_call, model_supports_temperature
from app.services.supabase_client import SessionRepository, get_client
from app.services.trend_service import TrendService


@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SCA trend report request received.")
    try:
        settings = Settings()

        secret = req.headers.get("x-marking-secret")
        if settings.marking_shared_secret and secret != settings.marking_shared_secret:
            return handle_response(error="Unauthorized", status_code=401)

        try:
            body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)

        candidate_id = body.get("candidateId") or body.get("candidate_id")
        if not candidate_id:
            return handle_response(error="candidateId is required", status_code=400)

        deployment = settings.azure_openai_marking_deployment
        api_version = settings.azure_openai_marking_api_version or settings.azure_openai_api_version
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=api_version,
        )
        temperature = 0.2 if model_supports_temperature(deployment) else None
        repo = SessionRepository(get_client(settings))
        service = TrendService(
            repo, make_azure_model_call(openai_client, deployment, temperature=temperature)
        )

        report = await service.generate(candidate_id)
        return handle_response(
            data={"status": "completed", "confidence": report.get("confidence")}
        )
    except Exception as exc:  # noqa: BLE001
        logging.error(f"Error generating trend report: {exc}")
        return handle_response(error=str(exc), status_code=500)
