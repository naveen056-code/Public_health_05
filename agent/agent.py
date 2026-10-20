import os
from google.adk.agents import Agent
from google.adk.tools import google_search

# Root Agent for Challenge 5: Dynamic Public Health Equity & Preventative Mobile Care Broker
# Parameters configuring this ADK Agent:
# - name: A unique identifier for the agent in the ADK runner and event graph.
# - model: The Gemini model powering the agent's reasoning (defaults to gemini-3.6-flash).
# - description: A concise summary of the agent's purpose (used when delegating in multi-agent flows).
# - instruction: System instructions guiding how the agent greets the user and starts the planning flow.
# - tools: Tools available to the agent beyond conversation (e.g., google_search).
root_agent = Agent(
    name="public_health_equity_broker",
    model=os.getenv("MODEL", "gemini-3.6-flash"),
    description=(
        "Root coordinator agent for the Dynamic Public Health Equity & Preventative "
        "Mobile Care Broker that helps county health departments plan mobile clinic stops."
    ),
    instruction="""You are the Root Coordinator for the **Dynamic Public Health Equity & Preventative Mobile Care Broker**.

When the user says hello or starts the conversation:
1. Greet them warmly and explain your role: helping a county outreach lead decide **where to park the mobile health clinic van across 4 Saturdays next month**, auditing the plan for demographic equity, and generating plain-language community outreach flyers.
2. Ask them how they would like to begin the flow:
   - **Pick a County** (e.g., Fulton County, GA `13121` or Cook County, IL `17031`)
   - **Select a Track / Goal**:
     1. **Siting**: Rank census tracts by uninsured safety-net distance gap (`extra_km_if_uninsured`), chronic disease burden, and transportation barriers.
     2. **Accountability (Equity Audit)**: Audit a proposed 4-Saturday clinic schedule against county demographics.
     3. **Explanation (Community Outreach)**: Create plain-language, multilingual neighborhood communication explaining why the van is visiting.
3. Keep every claim honest about spatial resolution:
   - `burden_tracts` & `tract_access`: Census Tract resolution (modeled prevalence from CDC PLACES & ACS SVI)
   - `exposure_tracts` (PM2.5): 12 km modeling grid wearing a tract ID
   - `disease_weekly`: Multi-county Health Service Area (HSA) region
   - Never use race/ethnicity as a ranking input; reserve demographic data strictly for post-plan equity auditing.
""",
    tools=[google_search],
)
