import os
import sys
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from services.narrative_mode_service import NarrativeModeService


class NarrativeModeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = NarrativeModeService()

    @patch("services.narrative_mode_service.generate_text")
    def test_build_plan_returns_scene_coherent_payload(self, generate_text_mock) -> None:
        generate_text_mock.side_effect = [
            "Uma história curta sobre um investidor iniciante.",
            "Ele começou com medo. Depois estudou. Então encontrou clareza. No fim, ganhou confiança.",
            '{"style":"cinematic","palette":"blue and gold","main_character":"young investor","setting":"modern office","camera_style":"vertical close-ups","mood":"hopeful","continuity_rules":["same character","same office"]}',
            '[{"scene_number":1,"purpose":"hook","narration":"Ele começou com medo.","image_prompt":"same young investor in a modern office, anxious expression, blue and gold cinematic lighting"},{"scene_number":2,"purpose":"turn","narration":"Depois estudou.","image_prompt":"same young investor studying charts in the same office, blue and gold cinematic lighting"}]',
        ]

        plan = self.service.build_plan(
            mode="story",
            niche="mercado financeiro",
            language="Portuguese",
        )

        self.assertEqual(plan["mode"], "story")
        self.assertEqual(plan["subject"], "Uma história curta sobre um investidor iniciante.")
        self.assertIn("same young investor", plan["scenes"][0]["image_prompt"])
        self.assertEqual(plan["visual_bible"]["style"], "cinematic")
        self.assertIn("Ele começou com medo.", plan["script"])

    @patch("services.narrative_mode_service.generate_text")
    def test_build_plan_respects_manual_topic_and_script(self, generate_text_mock) -> None:
        generate_text_mock.side_effect = [
            '{"style":"serene","palette":"warm gold","main_character":"narrator","setting":"ancient hillside","camera_style":"vertical wide shot","mood":"devotional","continuity_rules":["gentle light"]}',
            '[{"scene_number":1,"purpose":"opening","narration":"A fé começa no silêncio.","image_prompt":"serene hillside at sunrise, devotional cinematic composition"}]',
        ]

        plan = self.service.build_plan(
            mode="biblical",
            niche="mensagens bíblicas",
            language="Portuguese",
            topic_override="Reflexão sobre fé e coragem",
            script_override="A fé começa no silêncio.",
        )

        self.assertEqual(plan["subject"], "Reflexão sobre fé e coragem")
        self.assertEqual(plan["script"], "A fé começa no silêncio.")
        self.assertEqual(len(plan["scenes"]), 1)
        self.assertEqual(generate_text_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
