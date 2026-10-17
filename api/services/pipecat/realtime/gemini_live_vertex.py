"""EasyTech subclass of pipecat's Gemini Live Vertex AI LLM service.

Diamond inheritance: combines the EasyTech engine-integration overrides from
:class:`EasyTechGeminiLiveLLMService` with the Vertex-specific tweaks from
upstream's :class:`GeminiLiveVertexLLMService` (no history config,
``NON_BLOCKING`` tools disabled, service-account credentials).

MRO::

    EasyTechGeminiLiveVertexLLMService
      -> EasyTechGeminiLiveLLMService
      -> RealtimeConversationMixin
      -> GeminiLiveVertexLLMService
      -> GeminiLiveLLMService
      -> LLMService
      -> ...
"""

from api.services.pipecat.realtime.gemini_live import EasyTechGeminiLiveLLMService
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.google.gemini_live.vertex.llm import (
    GeminiLiveVertexLLMService,
)


class EasyTechGeminiLiveVertexLLMService(
    EasyTechGeminiLiveLLMService,
    GeminiLiveVertexLLMService,
):
    """Vertex AI variant of Gemini Live with EasyTech integration quirks."""

    pass


# Guard against MRO regressions: a future refactor that flips inheritance
# order or breaks the diamond would silently bypass the EasyTech overrides.
_mro = EasyTechGeminiLiveVertexLLMService.__mro__
assert _mro[1] is EasyTechGeminiLiveLLMService, (
    f"Expected EasyTechGeminiLiveLLMService at MRO[1], got {_mro[1]}"
)
assert _mro.index(GeminiLiveVertexLLMService) < _mro.index(GeminiLiveLLMService), (
    "Vertex overrides must precede the base Gemini implementation"
)
del _mro
