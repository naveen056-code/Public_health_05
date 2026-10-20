"""The planner's tools. Ours, not generic: they hold the judgment calls (what "needs the
van" means, how far apart four stops must be, where to refer people afterwards) so the
model does not reinvent them on every turn."""

from __future__ import annotations

from google.adk.tools import ToolContext

from . import data


def rank_tracts(
    top_n: int = 15,
    w_uninsured: float = 0.30,
    w_distance: float = 0.25,
    w_no_vehicle: float = 0.20,
    w_chronic: float = 0.15,
    w_no_checkup: float = 0.10,
) -> dict:
    """Ranks the county's census tracts by need for a mobile clinic.

    Each input is percent-ranked within the county and combined with the given weights:
    uninsured adults, straight-line km to a safety-net clinic, households with no
    vehicle, diabetes plus high blood pressure, and adults without a routine checkup.
    Air quality and respiratory trends are deliberately not inputs: they are not
    measured at tract scale.

    Args:
        top_n: How many of the highest-need tracts to return.
        w_uninsured: Weight on the uninsured rate.
        w_distance: Weight on km to the nearest safety-net site.
        w_no_vehicle: Weight on the share of households with no vehicle.
        w_chronic: Weight on diabetes and high blood pressure prevalence.
        w_no_checkup: Weight on adults who missed a routine checkup.

    Returns:
        The weights used and the top tracts, each value labelled with its scale.
    """
    weights = dict(uninsured=w_uninsured, distance=w_distance, no_vehicle=w_no_vehicle,
                   chronic=w_chronic, no_checkup=w_no_checkup)
    ranked = data.ranked_tracts(weights)
    return {"weights": weights, "tracts_ranked": len(ranked),
            "top": [data.tract_summary(r) for r in ranked[:top_n]]}


def plan_saturdays(
    tool_context: ToolContext,
    month: str = "",
    min_spacing_km: float = 5.0,
    min_km_to_safety_net: float = 3.0,
    w_uninsured: float = 0.30,
    w_distance: float = 0.25,
    w_no_vehicle: float = 0.20,
    w_chronic: float = 0.15,
    w_no_checkup: float = 0.10,
    exclude_geo_ids: list[str] | None = None,
    include_geo_ids: list[str] | None = None,
) -> dict:
    """Turns the need ranking into four Saturday stops for the van, and records them.

    Walks the ranking from the top, skipping tracts closer than min_km_to_safety_net to
    a safety-net clinic and tracts within min_spacing_km of a stop already chosen, so
    the four Saturdays reach four different areas. Attaches the nearest safety-net clinic
    to each stop for follow-up referrals. Saves the plan to session state as plan_stops,
    which is what the auditor and the explainer read.

    Args:
        month: Month to plan as 'YYYY-MM'. Empty means next calendar month.
        min_spacing_km: Minimum straight-line distance between any two stops.
        min_km_to_safety_net: Skip tracts already this close to a safety-net clinic.
        w_uninsured: Weight on the uninsured rate.
        w_distance: Weight on km to the nearest safety-net site.
        w_no_vehicle: Weight on the share of households with no vehicle.
        w_chronic: Weight on diabetes and high blood pressure prevalence.
        w_no_checkup: Weight on adults who missed a routine checkup.
        exclude_geo_ids: Tracts to leave out, e.g. after an audit objection.
        include_geo_ids: Tracts that must be included, e.g. a confirmed partner site.

    Returns:
        The stops with dates, reasons and referral sites, the runner-up tract, and the
        parameters used.
    """
    weights = dict(uninsured=w_uninsured, distance=w_distance, no_vehicle=w_no_vehicle,
                   chronic=w_chronic, no_checkup=w_no_checkup)
    ranked = data.ranked_tracts(weights)
    dates = data.saturdays(month or None)
    chosen = data.select_stops(ranked, stops=len(dates), min_spacing_km=min_spacing_km,
                               min_km_to_safety_net=min_km_to_safety_net,
                               exclude=exclude_geo_ids, include=include_geo_ids)
    referrals = data.nearest_safety_net([c["geo_id"] for c in chosen])

    stops = []
    for date, r in zip(dates, chosen):
        s = data.tract_summary(r)
        s["saturday"] = date
        s["refer_to"] = referrals.get(r["geo_id"])
        stops.append(s)

    chosen_ids = {s["geo_id"] for s in stops}
    runner_up = None
    for r in ranked:
        if r["geo_id"] in chosen_ids:
            continue
        runner_up = data.tract_summary(r)
        near = min(chosen, key=lambda c: data._km(r, c)) if chosen else None
        if r["geo_id"] in (exclude_geo_ids or []):
            runner_up["why_not"] = "left out on request"
        elif r["km_to_safety_net"] < min_km_to_safety_net:
            runner_up["why_not"] = (f"already {r['km_to_safety_net']:.1f} km from a safety-net "
                                    f"clinic, under the {min_km_to_safety_net} km threshold")
        elif near is not None and data._km(r, near) < min_spacing_km:
            runner_up["why_not"] = (f"{data._km(r, near):.1f} km from the {near['geo_id']} stop, "
                                    "close enough to share it")
        else:
            runner_up["why_not"] = "lower need score than the four chosen"
        break
    params = dict(month=month or dates[0][:7], min_spacing_km=min_spacing_km,
                  min_km_to_safety_net=min_km_to_safety_net, weights=weights,
                  exclude_geo_ids=exclude_geo_ids or [], include_geo_ids=include_geo_ids or [])

    # The comparison group for the equity audit: the top quarter of the county by need.
    # Stored as tract IDs only, so the auditor can join demographics the planner never sees.
    need_pool = [r["geo_id"] for r in ranked[: max(4, len(ranked) // 4)]]

    state = tool_context.state
    state["plan_stops"] = stops
    state["plan_params"] = params
    state["plan_runner_up"] = runner_up
    state["need_pool_geo_ids"] = need_pool
    state["plan_versions"] = state.get("plan_versions", []) + [
        {"version": len(state.get("plan_versions", [])) + 1,
         "geo_ids": [s["geo_id"] for s in stops], "params": params}]

    return {"stops": stops, "runner_up": runner_up, "params": params,
            "note": "Saved to session state as plan_stops."}
