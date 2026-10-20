"""Community helper, text chat. Answers residents from the published plan."""

from google.adk.agents import LlmAgent
from google.genai import types

from clinic_broker import config

from .core import INSTRUCTION, TOOLS

root_agent = LlmAgent(
    name="community_helper",
    model=config.MODEL,
    description="Answers residents' questions about the mobile clinic schedule, in English or Spanish.",
    instruction=INSTRUCTION,
    tools=TOOLS,
    generate_content_config=types.GenerateContentConfig(temperature=0.4),
)
