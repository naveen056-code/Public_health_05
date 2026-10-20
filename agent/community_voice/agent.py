"""Community helper, live voice. Same instruction and tools as the text helper, on
Gemini's Live native-audio model, which in the lab project is served from us-central1
only (the text models are served from global only)."""

import os

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from pydantic import Field

from community_helper.core import INSTRUCTION, TOOLS, VOICE_NOTE

LIVE_MODEL = os.environ.get("A4I_LIVE_MODEL", "gemini-live-2.5-flash-native-audio")
LIVE_LOCATION = os.environ.get("A4I_LIVE_LOCATION", "us-central1")


class RegionalGemini(Gemini):
    """Gemini pinned to one location, whatever GOOGLE_CLOUD_LOCATION says."""

    client_kwargs: dict = Field(default_factory=lambda: {"location": LIVE_LOCATION})


root_agent = LlmAgent(
    name="community_voice",
    model=RegionalGemini(model=LIVE_MODEL),
    description="Talks with residents about the mobile clinic schedule, in English or Spanish.",
    instruction=INSTRUCTION + VOICE_NOTE,
    tools=TOOLS,
)
