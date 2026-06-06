"""HTTP trigger: grade one completed SCA consultation and persist the feedback.

POST /api/mark-consultation  body: { "sessionId": "<uuid>" }
Guarded by a shared secret header (x-marking-secret) so only the frontend's
generate-feedback route can trigger it. Source: FF SCA Build Package, Part 1.
"""
import logging

import azure.functions as func
from openai import AsyncAzureOpenAI

from app.config import Settings
from app.middleware import cors_middleware, handle_response
from app.services.marking_service import (
    MarkingService,
    make_azure_model_call,
    model_supports_temperature,
)
from app.services.supabase_client import SessionRepository, get_client


@cors_middleware
async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SCA marking request received.")
    try:
        settings = Settings()

        secret = req.headers.get("x-marking-secret")
        if settings.marking_shared_secret and secret != settings.marking_shared_secret:
            return handle_response(error="Unauthorized", status_code=401)

        try:
            body = req.get_json()
        except ValueError:
            return handle_response(error="Invalid request body", status_code=400)

        session_id = body.get("sessionId") or body.get("session_id")
        if not session_id:
            return handle_response(error="sessionId is required", status_code=400)

        deployment = settings.azure_openai_marking_deployment
        api_version = settings.azure_openai_marking_api_version or settings.azure_openai_api_version
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=api_version,
        )
        temperature = 0.2 if model_supports_temperature(deployment) else None
        repo = SessionRepository(get_client(settings))
        service = MarkingService(
            repo,
            make_azure_model_call(openai_client, deployment, temperature=temperature),
        )

        result = await service.mark(session_id)
        return handle_response(
            data={
                "status": "completed",
                "verdict": result["overall"]["verdict"],
                "weighted_score": result["overall"]["weighted_score"],
            }
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean 500 to the caller
        logging.error(f"Error marking consultation: {exc}")
        return handle_response(error=str(exc), status_code=500)
