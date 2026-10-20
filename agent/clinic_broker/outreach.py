"""The neighborhood handout: the explainer's words, our facts, on a printable page.

The explainer writes only the parts that need a voice: a headline, a short invitation and
a text message, in English and Spanish. Everything that must be right (the date, the
clinic to go to afterwards, its address and hours, what the van offers) is filled in
here from state, so the model cannot get it wrong."""

from __future__ import annotations

import datetime as dt
import html

from pydantic import BaseModel, Field

from . import config


class StopMessage(BaseModel):
    geo_id: str = Field(description="The stop's tract ID, copied exactly from the stops list.")
    headline_en: str = Field(description="Flyer headline in English, at most 8 words.")
    invitation_en: str = Field(description="Two or three short, warm sentences in English.")
    sms_en: str = Field(description="English text message, under 300 characters.")
    headline_es: str = Field(description="Flyer headline in Spanish, at most 8 words.")
    invitation_es: str = Field(description="Two or three short, warm sentences in Spanish.")
    sms_es: str = Field(description="Spanish text message, under 300 characters.")


class Outreach(BaseModel):
    stops: list[StopMessage]
    why_not_us_en: str = Field(description="Script for a community health worker, English.")
    why_not_us_es: str = Field(description="The same script in natural Spanish.")


_OFFER = {
    "en": ["Free blood pressure check", "Free blood sugar check",
           "See a nurse practitioner", "You do not need insurance"],
    "es": ["Revisión gratis de la presión arterial", "Revisión gratis del azúcar en la sangre",
           "Atención con una enfermera practicante", "No necesita seguro médico"],
}
_LABELS = {
    "en": dict(when="When", where="Where", time="Time", after="For follow-up care, visit",
               hours="hours a week", no_hours="call for hours", free="Free mobile health clinic"),
    "es": dict(when="Cuándo", where="Dónde", time="Hora", after="Para seguimiento, visite",
               hours="horas a la semana", no_hours="llame para saber el horario",
               free="Clínica móvil de salud gratis"),
}
_MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
              "septiembre", "octubre", "noviembre", "diciembre"]


def date_label(iso: str, lang: str) -> str:
    d = dt.date.fromisoformat(iso)
    if lang == "es":
        return f"sábado {d.day} de {_MONTHS_ES[d.month - 1]}"
    return d.strftime("Saturday, %B ") + str(d.day)


def _messages_by_stop(outreach: dict) -> dict[str, dict]:
    return {m["geo_id"]: m for m in outreach.get("stops", [])}


def as_markdown(outreach: dict, stops: list[dict]) -> str:
    msgs = _messages_by_stop(outreach)
    out = ["### Text messages"]
    for s in stops:
        m = msgs.get(s["geo_id"])
        if not m:
            out.append(f"\n**{date_label(s['saturday'], 'en')}**: *(no message written for this stop)*")
            continue
        out.append(f"\n**{date_label(s['saturday'], 'en')}**\n\n- EN: {m['sms_en']}\n- ES: {m['sms_es']}")
    out.append("\n### For the neighborhood we did not pick\n")
    out.append(f"**English:** {outreach.get('why_not_us_en', '')}\n")
    out.append(f"**Español:** {outreach.get('why_not_us_es', '')}")
    return "\n".join(out)


def _half(lang: str, stop: dict, msg: dict) -> str:
    e = html.escape
    lab = _LABELS[lang]
    ref = stop.get("refer_to") or {}
    hours = (f"{int(ref['hours_per_week'])} {lab['hours']}" if ref.get("hours_per_week")
             else lab["no_hours"])
    offer = "".join(f"<li>{e(x)}</li>" for x in _OFFER[lang])
    return f"""
  <section class="half" lang="{lang}">
    <p class="kicker">{e(lab['free'])}</p>
    <h1>{e(msg[f'headline_{lang}'])}</h1>
    <p class="invite">{e(msg[f'invitation_{lang}'])}</p>
    <div class="cols">
      <ul class="offer">{offer}</ul>
      <dl class="when">
        <dt>{e(lab['when'])}</dt><dd>{e(date_label(stop['saturday'], lang))}</dd>
        <dt>{e(lab['time'])}</dt><dd class="blank">&nbsp;</dd>
        <dt>{e(lab['where'])}</dt><dd class="blank">&nbsp;</dd>
      </dl>
    </div>
    <p class="after">{e(lab['after'])} <b>{e(ref.get('display_name') or ref.get('name', ''))}</b>,
      {e(ref.get('address', ''))}, {e(ref.get('city', ''))} · {e(hours)}</p>
  </section>"""


def as_html(outreach: dict, stops: list[dict]) -> str:
    msgs = _messages_by_stop(outreach)
    pages = []
    for s in stops:
        m = msgs.get(s["geo_id"])
        if m:
            pages.append(f'<article class="page">{_half("en", s, m)}'
                         f'<hr class="cut">{_half("es", s, m)}</article>')
    e = html.escape
    pages.append(f"""<article class="page script">
  <section class="half" lang="en"><p class="kicker">For community health workers</p>
    <h1>If someone asks "why not us?"</h1><p class="invite">{e(outreach.get('why_not_us_en', ''))}</p></section>
  <hr class="cut">
  <section class="half" lang="es"><p class="kicker">Para promotores de salud</p>
    <h1>Si alguien pregunta "¿por qué no aquí?"</h1><p class="invite">{e(outreach.get('why_not_us_es', ''))}</p></section>
</article>""")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mobile clinic flyers · {e(config.COUNTY_NAME)}</title>
<style>
  :root {{ --ink:#1b1b1b; --accent:#0b6e4f; --muted:#555; --paper:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#eee; color:var(--ink); font:16px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .page {{ background:var(--paper); width:8.5in; min-height:11in; margin:16px auto; padding:0.5in;
          display:flex; flex-direction:column; gap:0.2in; }}
  .half {{ flex:1; }}
  .kicker {{ margin:0; color:var(--accent); font-weight:700; text-transform:uppercase; letter-spacing:.06em; font-size:13px; }}
  h1 {{ margin:.1in 0; font-size:34px; line-height:1.1; }}
  .invite {{ font-size:19px; margin:0 0 .15in; }}
  .cols {{ display:flex; gap:.3in; }}
  .offer {{ flex:1; margin:0; padding-left:1.1em; font-size:18px; }}
  .offer li {{ margin:.04in 0; }}
  .when {{ flex:1; margin:0; display:grid; grid-template-columns:auto 1fr; gap:.06in .15in; font-size:18px; }}
  .when dt {{ font-weight:700; }} .when dd {{ margin:0; }}
  .blank {{ border-bottom:1.5px solid var(--ink); min-width:2in; }}
  .after {{ margin:.15in 0 0; color:var(--muted); font-size:15px; }}
  .cut {{ border:0; border-top:2px dashed #999; margin:0; }}
  @media print {{ body {{ background:none; }} .page {{ margin:0; page-break-after:always; }} }}
  @media (max-width:9in) {{ .page {{ width:auto; min-height:0; margin:16px; padding:16px; }} .cols {{ flex-direction:column; }} }}
</style></head>
<body>
{''.join(pages)}
</body></html>"""
