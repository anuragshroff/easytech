"""Azure authentication and transport with EasyTech's OpenAI realtime behavior."""

from api.services.pipecat.realtime.openai_realtime import EasyTechOpenAIRealtimeLLMService
from pipecat.services.azure.realtime.llm import AzureRealtimeLLMService


class EasyTechAzureRealtimeLLMService(
    EasyTechOpenAIRealtimeLLMService, AzureRealtimeLLMService
):
    """Share OpenAI conversation handling while retaining Azure's constructor."""
