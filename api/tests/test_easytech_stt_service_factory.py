from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs

import pytest
from pipecat.services.settings import NOT_GIVEN
from pipecat.transcriptions.language import Language

from api.services.configuration.registry import EasyTechSTTService, ServiceProviders
from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.service_factory import (
    create_stt_service,
    easytech_stt_uses_flux_language,
    stt_uses_external_turns,
)


def _audio_config() -> AudioConfig:
    return AudioConfig(
        transport_in_sample_rate=16000,
        transport_out_sample_rate=16000,
    )


def _easytech_config(language: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        stt=SimpleNamespace(
            provider=ServiceProviders.DOGRAH.value,
            api_key="mps-key",
            model="default",
            language=language,
        )
    )


@pytest.mark.parametrize(
    ("language", "uses_flux"),
    [
        (None, True),
        ("multi", True),
        ("es", True),
        ("en-GB", True),
        ("pt-BR", True),
        ("fr-CA", True),
        ("es-419", True),
        ("EN-gb", True),
        ("ar", False),
        ("ar-SA", False),
        ("zh-CN", False),
        ("ko-KR", False),
    ],
)
def test_easytech_flux_routing_and_turn_strategies_agree(language, uses_flux):
    assert easytech_stt_uses_flux_language(language) is uses_flux
    assert stt_uses_external_turns(_easytech_config(language)) is uses_flux


def test_create_easytech_multi_uses_flux_service_without_language_hint():
    user_config = _easytech_config("multi")

    with (
        patch(
            "api.services.pipecat.service_factory.EasyTechFluxSTTService"
        ) as flux_service,
        patch("api.services.pipecat.service_factory.EasyTechSTTService") as stt_service,
    ):
        create_stt_service(user_config, _audio_config(), correlation_id="corr-123")

    flux_service.assert_called_once()
    stt_service.assert_not_called()
    kwargs = flux_service.call_args.kwargs
    assert kwargs["correlation_id"] == "corr-123"
    assert kwargs["settings"].model == "flux-general-multi"
    assert kwargs["settings"].language_hints is NOT_GIVEN


@pytest.mark.parametrize(
    ("language", "hint"),
    [("es", Language.ES), ("en-GB", Language.EN), ("pt-BR", Language.PT)],
)
def test_create_easytech_supported_language_uses_flux_service_with_hint(language, hint):
    user_config = _easytech_config(language)

    with (
        patch(
            "api.services.pipecat.service_factory.EasyTechFluxSTTService"
        ) as flux_service,
        patch("api.services.pipecat.service_factory.EasyTechSTTService") as stt_service,
    ):
        create_stt_service(user_config, _audio_config(), keyterms=["EasyTech"])

    flux_service.assert_called_once()
    stt_service.assert_not_called()
    kwargs = flux_service.call_args.kwargs
    assert kwargs["settings"].model == "flux-general-multi"
    assert kwargs["settings"].language_hints == [hint]
    assert kwargs["settings"].keyterm == ["EasyTech"]


@pytest.mark.parametrize(
    ("language", "hints"),
    [("multi", ["en", "es"]), ("en-GB", ["EN-US", "es", "es-419"])],
)
def test_easytech_flux_sends_combined_language_hints_to_proxy(language, hints):
    config = SimpleNamespace(
        stt=EasyTechSTTService(api_key="mps-key", language=language, language_hints=hints)
    )
    service = create_stt_service(config, _audio_config(), correlation_id="corr-123")

    query = parse_qs(service._build_easytech_query_string())
    assert query["model"] == ["flux-general-multi"]
    assert query["language_hint"] == ["en", "es"]
    assert query["correlation_id"] == ["corr-123"]


def test_easytech_stt_rejects_unsupported_language_hints():
    with pytest.raises(
        ValueError, match="Unsupported Flux multilingual language hints: ta"
    ):
        EasyTechSTTService(api_key="mps-key", language_hints=["en", "ta"])


@pytest.mark.parametrize("language", ["ar", "ar-SA", "zh-CN", "ko-KR"])
def test_create_easytech_unsupported_language_falls_back_to_standard_stt_service(
    language,
):
    user_config = _easytech_config(language)
    # Saved Flux hints must not change routing for a non-Flux language.
    user_config.stt.language_hints = ["en", "es"]

    with (
        patch(
            "api.services.pipecat.service_factory.EasyTechFluxSTTService"
        ) as flux_service,
        patch("api.services.pipecat.service_factory.EasyTechSTTService") as stt_service,
    ):
        create_stt_service(
            user_config,
            _audio_config(),
            keyterms=["EasyTech"],
            correlation_id="corr-123",
        )

    flux_service.assert_not_called()
    stt_service.assert_called_once()
    kwargs = stt_service.call_args.kwargs
    assert kwargs["correlation_id"] == "corr-123"
    assert kwargs["settings"].model == "default"
    assert kwargs["settings"].language == language
    assert kwargs["keyterms"] == ["EasyTech"]
