# Agents module
# Configure Azure OpenAI client for text agents (feedback) so the SDK targets Azure
from openai import AsyncAzureOpenAI
from agents import set_default_openai_client, set_default_openai_api, set_tracing_disabled
from ..config import settings

# Use Chat Completions API instead of Responses API (Azure doesn't support Responses on older versions)
set_default_openai_api("chat_completions")

# Disable tracing (Azure keys don't work with OpenAI's trace ingestion endpoint)
set_tracing_disabled(True)

# Use Azure deployment + api-version for chat/text calls
# Use chat-specific key if provided, otherwise fall back to primary key
_chat_api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY

_azure_client = AsyncAzureOpenAI(
    api_key=_chat_api_key,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_CHAT_API_VERSION,
    azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
)
set_default_openai_client(_azure_client)

from .patient import get_patient_agent, PATIENT_PROMPT
from .feedback import feedback_agent, generate_feedback

__all__ = ["get_patient_agent", "PATIENT_PROMPT", "feedback_agent", "generate_feedback"]
