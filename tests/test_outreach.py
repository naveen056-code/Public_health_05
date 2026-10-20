import unittest

from clinic_broker import outreach
from clinic_broker.outreach import Outreach, StopMessage


class TestOutreachModule(unittest.TestCase):
    def test_date_label(self):
        iso = "2026-11-07"
        self.assertEqual(outreach.date_label(iso, "en"), "Saturday, November 7")
        self.assertEqual(outreach.date_label(iso, "es"), "sábado 7 de noviembre")

    def test_outreach_models_validation(self):
        msg = StopMessage(
            geo_id="13121000100",
            headline_en="Free health checks this Saturday",
            invitation_en="Join us for free wellness checks in your neighborhood.",
            sms_en="Free health clinic Sat Nov 7 at [parking spot] from [time]. No insurance needed.",
            headline_es="Chequeos de salud gratuitos este sábado",
            invitation_es="Acompáñenos para chequeos médicos gratuitos.",
            sms_es="Clínica móvil sáb 7 nov en [parking spot] a las [time]. Sin seguro médico.",
        )
        self.assertEqual(msg.geo_id, "13121000100")

        outreach_data = Outreach(
            stops=[msg],
            why_not_us_en="We prioritize areas with least clinic access.",
            why_not_us_es="Damos prioridad a zonas con menor acceso a clínicas.",
        )
        self.assertEqual(len(outreach_data.stops), 1)

    def test_as_markdown(self):
        outreach_dict = {
            "stops": [
                {
                    "geo_id": "13121000100",
                    "sms_en": "Free health clinic Sat Nov 7 at [parking spot].",
                    "sms_es": "Clínica móvil sáb 7 nov en [parking spot].",
                }
            ],
            "why_not_us_en": "Explanation in English.",
            "why_not_us_es": "Explicación en español.",
        }
        stops = [{"geo_id": "13121000100", "saturday": "2026-11-07"}]
        md = outreach.as_markdown(outreach_dict, stops)
        self.assertIn("### Text messages", md)
        self.assertIn("Free health clinic Sat Nov 7", md)
        self.assertIn("Explanation in English.", md)
        self.assertIn("Explicación en español.", md)

    def test_as_html(self):
        outreach_dict = {
            "stops": [
                {
                    "geo_id": "13121000100",
                    "headline_en": "Free Health Check",
                    "invitation_en": "Welcome everyone & family.",
                    "sms_en": "Text EN",
                    "headline_es": "Chequeo Gratis",
                    "invitation_es": "Bienvenidos todos.",
                    "sms_es": "Texto ES",
                }
            ]
        }
        stops = [
            {
                "geo_id": "13121000100",
                "saturday": "2026-11-07",
                "refer_to": {
                    "name": "Family Health Center",
                    "display_name": "Family Health Center",
                    "address": "123 Main St",
                    "city": "Atlanta",
                    "hours_per_week": 40,
                },
            }
        ]
        html_content = outreach.as_html(outreach_dict, stops)
        self.assertIn("<!doctype html>", html_content)
        self.assertIn("Free Health Check", html_content)
        self.assertIn("Chequeo Gratis", html_content)
        self.assertIn("123 Main St", html_content)
        self.assertIn("40 hours a week", html_content)
        # Ensure HTML escaping worked on '&'
        self.assertIn("&amp;", html_content)


if __name__ == "__main__":
    unittest.main()
