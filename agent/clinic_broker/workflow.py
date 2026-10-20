"""Three small agents that need no model: they move data, not judgment."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Callable

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types


def _text(s: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=s)])


class EvidenceAgent(BaseAgent):
    """Runs one fixed lookup and writes the result to its own state key.

    Several of these run under a ParallelAgent. Parallel branches share one state dict,
    so each writes a distinct key; two branches writing the same key would leave one
    value and no error."""

    fetch: Callable[[], dict]
    state_key: str

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        result = await asyncio.to_thread(self.fetch)
        yield Event(
            author=self.name, invocation_id=ctx.invocation_id, branch=ctx.branch,
            content=_text(f"`{self.state_key}` gathered ({len(json.dumps(result, default=str)):,} chars)."),
            actions=EventActions(state_delta={self.state_key: result}),
        )


class WhenAgent(BaseAgent):
    """Runs its one sub-agent only when `condition(state)` is true."""

    condition: Callable[[dict], bool]
    skipped_message: str = "Skipped."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not self.condition(ctx.session.state):
            yield Event(author=self.name, invocation_id=ctx.invocation_id, branch=ctx.branch,
                        content=_text(self.skipped_message))
            return
        async for event in self.sub_agents[0].run_async(ctx):
            yield event


class ClinicPlanReport(BaseAgent):
    """Assembles the four-part Clinic Plan from what the other agents left in state."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        s = ctx.session.state
        versions = s.get("plan_versions", [])
        audits = s.get("audit_history", [])

        trail = []
        for a in audits:
            trail.append(f"- Audit round {a['round']} (plan v{a['plan_version']}): **{a['verdict']}**")
        if len(versions) > 1:
            first, last = versions[0]["geo_ids"], versions[-1]["geo_ids"]
            dropped = [g for g in first if g not in last]
            added = [g for g in last if g not in first]
            trail.append(f"- Stops changed between v1 and v{len(versions)}: "
                         f"dropped {dropped or 'none'}, added {added or 'none'}")
        final = s.get("audit_verdict")
        if final == "REVISE":
            trail.append("- **The auditor still objects to the final plan.** Its last report is "
                         "below; the outreach lead decides.")

        last_audit = audits[-1]["report"] if audits else "(no audit ran)"
        body = "\n\n".join([
            "# Clinic Plan",
            "## 1. Where the van goes, and why\n\n" + s.get("plan", "(no plan)"),
            "## 2. Who this plan lands on: the equity audit\n\n" + "\n".join(trail)
            + "\n\n<details><summary>Final audit report</summary>\n\n" + last_audit + "\n\n</details>",
            "## 3. What we hand to the neighborhood\n\n" + s.get("flyer", "(no flyer)"),
        ])
        # Part 4, "what we could not tell you", is a required section of the plan itself.
        yield Event(author=self.name, invocation_id=ctx.invocation_id, branch=ctx.branch,
                    content=_text(body))
