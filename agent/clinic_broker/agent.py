"""The Clinic Plan pipeline.

    evidence (parallel)   need · context · capacity          -> evidence_* keys
    planner               ranks and picks four Saturdays     -> plan, plan_stops
    review loop (<=3)     auditor -> reviser if REVISE       -> audit_report, plan
    explainer             plain-language, English + Spanish  -> flyer
    report                assembles the Clinic Plan

Who can see what is the design:
- the planner and reviser reach data only through tools.py, which never reads race;
- the auditor is the only agent with the BigQuery MCP tool, and the only one whose
  instruction carries the Census join. It runs with include_contents="none", so it
  sees the plan but not the planner's reasoning, and cannot be talked into defending it;
- the explainer sees the final stops only, never the analysis.
"""

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.genai import types

from . import audit, config, data, prompts, tools
from .workflow import ClinicPlanReport, EvidenceAgent, WhenAgent

MAX_REVISIONS = 2

_precise = types.GenerateContentConfig(temperature=0.2)


def _planner(name: str, instruction: str, include_contents: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=config.MODEL,
        description="Picks four Saturday stops for the mobile clinic from need and access data.",
        instruction=instruction,
        tools=[tools.plan_saturdays, tools.rank_tracts],
        output_key="plan",
        include_contents=include_contents,
        generate_content_config=_precise,
    )


evidence = ParallelAgent(
    name="gather_evidence",
    description="Three independent lookups, run concurrently.",
    sub_agents=[
        EvidenceAgent(name="need_lookup", fetch=data.need_evidence, state_key="evidence_need"),
        EvidenceAgent(name="context_lookup", fetch=data.context_evidence, state_key="evidence_context"),
        EvidenceAgent(name="capacity_lookup", fetch=data.capacity_evidence, state_key="evidence_capacity"),
    ],
)

planner = _planner("planner", prompts.PLANNER, include_contents="default")

auditor = LlmAgent(
    name="auditor",
    model=config.MODEL,
    description="Independent equity and evidence audit of the current plan.",
    instruction=audit.auditor_instruction,
    tools=[audit.bigquery_mcp()],
    output_key="audit_report",
    include_contents="none",
    generate_content_config=_precise,
    after_agent_callback=audit.record_verdict,
)


def _count_revision(callback_context):
    callback_context.state["revisions"] = callback_context.state.get("revisions", 0) + 1
    return None


reviser = _planner("reviser", prompts.REVISER, include_contents="none")
reviser.after_agent_callback = _count_revision

review_loop = LoopAgent(
    name="review_loop",
    description="Audit, and revise if the audit says so. Always ends on an audit.",
    max_iterations=MAX_REVISIONS + 1,
    sub_agents=[
        auditor,
        WhenAgent(
            name="revise_if_rejected",
            condition=lambda s: s.get("audit_verdict") == "REVISE"
            and s.get("revisions", 0) < MAX_REVISIONS,
            skipped_message="No revision: the audit passed or the revision limit was reached.",
            sub_agents=[reviser],
        ),
    ],
)

explainer = LlmAgent(
    name="explainer",
    model=config.MODEL,
    description="Writes the bilingual neighborhood messages for the final stops.",
    instruction=prompts.EXPLAINER,
    output_key="flyer",
    include_contents="none",
    generate_content_config=types.GenerateContentConfig(temperature=0.7),
)

root_agent = SequentialAgent(
    name="clinic_plan",
    description=f"Plans next month's mobile clinic Saturdays for {config.COUNTY_NAME}.",
    sub_agents=[evidence, planner, review_loop, explainer, ClinicPlanReport(name="clinic_plan_report")],
)
