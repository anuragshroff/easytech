#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""EasyTech unified AI services for Pipecat.

This module provides unified access to various AI services through a single
EasyTech API endpoint, abstracting away provider-specific implementations.
"""

from pipecat.services.easytech.flux.stt import EasyTechFluxSTTService
from pipecat.services.easytech.llm import EasyTechLLMService
from pipecat.services.easytech.stt import EasyTechSTTService, EasyTechSTTSettings
from pipecat.services.easytech.tts import EasyTechTTSService, EasyTechTTSSettings

__all__ = [
    "EasyTechFluxSTTService",
    "EasyTechLLMService",
    "EasyTechSTTService",
    "EasyTechSTTSettings",
    "EasyTechTTSService",
    "EasyTechTTSSettings",
]
