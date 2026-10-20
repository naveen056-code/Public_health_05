"""The Clinic Plan pipeline.

    evidence (parallel)   need · context · capacity lookups  -> evidence_* keys
                          request reviewer: guidelines check -> request_review
    planner               ranks and picks four Saturdays     -> plan, plan_stops
    review loop (<=3)     auditor -> reviser if REVISE       -> audit_report, audit_table, plan
    outputs (parallel)    explainer: neighbors, EN + ES      -> outreach
                          accountability writer: funder      -> accountability
    report                assembles the Clinic Plan, saves the printable flyer and the
                          accountability statement as artifacts

Who can see what is the design:
- the planner and reviser reach data only through tools.py, which never reads race;
- the auditor is the only agent with the BigQuery MCP tool, and the only one whose
  instruction carries the Census join. It runs with include_contents="none", so it
  sees the plan but not the planner's reasoning, and cannot be talked into defending it;
- the explainer sees the final stops only, never the analysis;
- the accountability writer sees computed facts and the audit's own table, never the
  raw tables, and is told to add no number the facts do not contain.
"""

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.genai import types

from . import accountability, audit, config, data, prompts, review, tools
from .outreach import Outreach
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


# Judges the outreach lead's request against the guidelines. It needs none of the evidence,
# so it runs alongside the lookups and costs no extra time.
request_reviewer = LlmAgent(
    name="request_reviewer",
    model=config.MODEL,
    description="Checks the outreach lead's request against the guidelines before planning.",
    instruction=review.INSTRUCTION,
    output_schema=review.RequestReview,
    output_key="request_review",
    generate_content_config=_precise,
)

evidence = ParallelAgent(
    name="gather_evidence",
    description="Three independent lookups and the request review, run concurrently.",
    sub_agents=[
        EvidenceAgent(name="need_lookup", fetch=data.need_evidence, state_key="evidence_need"),
        EvidenceAgent(name="context_lookup", fetch=data.context_evidence, state_key="evidence_context"),
        EvidenceAgent(name="capacity_lookup", fetch=data.capacity_evidence, state_key="evidence_capacity"),
        request_reviewer,
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
    after_tool_callback=accountability.capture_audit_table,
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
    description="Writes the bilingual neighborhood flyer and text messages for the final stops.",
    instruction=prompts.EXPLAINER,
    output_schema=Outreach,
    output_key="outreach",
    include_contents="none",
    generate_content_config=types.GenerateContentConfig(temperature=0.7),
)

accountability_writer = LlmAgent(
    name="accountability_writer",
    model=config.MODEL,
    description="Writes the plan up for a funder or program director.",
    instruction=accountability.instruction,
    output_key="accountability",
    include_contents="none",
    generate_content_config=_precise,
)

# Both read only the final plan, and write different keys, so they run side by side.
outputs = ParallelAgent(
    name="write_outputs",
    description="The neighborhood handout and the funder statement, written concurrently.",
    sub_agents=[explainer, accountability_writer],
)

root_agent = SequentialAgent(
    name="clinic_plan",
    description=f"Plans next month's mobile clinic Saturdays for {config.COUNTY_NAME}.",
    sub_agents=[evidence, planner, review_loop, outputs, ClinicPlanReport(name="clinic_plan_report")],
)
