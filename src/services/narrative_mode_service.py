import json
import re

from config import get_image_generation_config
from config import get_storytelling_config
from llm_provider import generate_text


MODE_LABELS = {
    "story": "storytelling / comedy",
    "finance": "financial commentary",
    "biblical": "biblical devotional",
}

DEFAULT_SCENE_COUNTS = {
    "story": 6,
    "finance": 5,
    "biblical": 5,
}


class NarrativeModeService:
    def build_plan(
        self,
        mode: str,
        niche: str,
        language: str,
        topic_override: str | None = None,
        script_override: str | None = None,
        scene_count_override: int | None = None,
    ) -> dict:
        mode = str(mode or "story").strip().lower()
        storytelling = get_storytelling_config()
        image_generation = get_image_generation_config()
        requested_scene_count = scene_count_override or self._infer_requested_scene_count(topic_override or script_override or "")
        base_scene_count = max(
            storytelling.get("default_scene_count", DEFAULT_SCENE_COUNTS.get(mode, 5)),
            DEFAULT_SCENE_COUNTS.get(mode, 5),
        )
        scene_count = min(120, max(3, requested_scene_count or base_scene_count))

        subject = str(topic_override or "").strip() or self.generate_subject(
            mode=mode,
            niche=niche,
            language=language,
        )

        script = str(script_override or "").strip() or self.generate_script(
            mode=mode,
            subject=subject,
            language=language,
            scene_count=scene_count,
        )

        visual_bible = self.generate_visual_bible(
            mode=mode,
            subject=subject,
            language=language,
            consistency_level=image_generation.get("consistency_level", "high"),
            character_persistence=storytelling.get("character_persistence", True),
        )

        scenes = self.generate_scenes(
            mode=mode,
            subject=subject,
            script=script,
            language=language,
            visual_bible=visual_bible,
            scene_count=scene_count,
        )

        if scenes:
            script = "\n".join(
                str(scene.get("narration", "")).strip()
                for scene in scenes
                if str(scene.get("narration", "")).strip()
            ).strip() or script

        return {
            "mode": mode,
            "mode_label": MODE_LABELS.get(mode, mode),
            "subject": subject,
            "script": script,
            "visual_bible": visual_bible,
            "scenes": scenes,
            "scene_count": scene_count,
        }

    def generate_subject(self, mode: str, niche: str, language: str) -> str:
        prompt = f"""
        Generate one short-form YouTube Shorts topic for the content mode '{mode}'.
        Channel niche: {niche}
        Language: {language}

        Requirements:
        - One sentence only.
        - Highly clickable but clear.
        - Match the mode '{mode}'.
        - No markdown.
        - Return only the topic.
        """
        return self._clean_text(generate_text(prompt))

    def generate_script(self, mode: str, subject: str, language: str, scene_count: int) -> str:
        mode_instructions = {
            "story": "Tell a coherent mini-story with a hook, progression, escalation, reveal, and payoff. Keep the same protagonist, location logic, and threat logic. Do not introduce random new characters, children, or relationships unless they were already established. Every beat must clearly follow the previous beat.",
            "finance": "Explain the market topic clearly, with a strong hook, concise reasoning, real-world relevance, and an actionable conclusion.",
            "biblical": "Create a reverent, inspiring, and accessible devotional reflection rooted in biblical values and a clear spiritual takeaway.",
        }
        prompt = f"""
        Write a vertical-video narration in {language}.
        Subject: {subject}
        Mode: {mode}
        Guidance: {mode_instructions.get(mode, '')}

        Requirements:
        - Use exactly {scene_count} narration beats.
        - Each beat should be one short sentence.
        - Beat 1 must hook attention immediately.
        - Middle beats must progress logically.
        - Final beat must resolve, reveal, or land emotionally.
        - Keep entity continuity exact across all beats.
        - No markdown.
        - No numbering.
        - Return only the final narration text.
        """
        return self._clean_text(generate_text(prompt))

    def generate_visual_bible(
        self,
        mode: str,
        subject: str,
        language: str,
        consistency_level: str,
        character_persistence: bool,
    ) -> dict:
        prompt = f"""
        Create a compact visual bible in JSON for a vertical AI-generated short.
        Subject: {subject}
        Mode: {mode}
        Language: {language}
        Consistency level: {consistency_level}
        Character persistence required: {character_persistence}

        Return only valid JSON with this structure:
        {{
          "style": "...",
          "palette": "...",
          "main_character": "...",
          "setting": "...",
          "camera_style": "...",
          "mood": "...",
          "continuity_rules": ["...", "..."]
        }}
        """
        response = generate_text(prompt)
        parsed = self._parse_json_object(response)
        if parsed:
            return parsed
        return {
            "style": "cinematic vertical storytelling illustration",
            "palette": "balanced, vivid, high-contrast",
            "main_character": subject,
            "setting": mode,
            "camera_style": "vertical, expressive close-ups, medium shots",
            "mood": MODE_LABELS.get(mode, mode),
            "continuity_rules": [
                "keep visual continuity across scenes",
                "keep the same subject and tone throughout the sequence",
            ],
        }

    def generate_scenes(
        self,
        mode: str,
        subject: str,
        script: str,
        language: str,
        visual_bible: dict,
        scene_count: int,
    ) -> list[dict]:
        prompt = f"""
        Break the following narration into {scene_count} coherent scenes for AI image generation.

        Subject: {subject}
        Mode: {mode}
        Language: {language}
        Script: {script}
        Visual bible: {json.dumps(visual_bible, ensure_ascii=False)}

        Return only valid JSON as an array.
        Each item must have:
        - scene_number
        - narration
        - image_prompt
        - purpose

        Rules:
        - image prompts must keep strict continuity between scenes
        - keep the same protagonist, relationships, and setting logic unless the script explicitly changes them
        - do not invent children, friends, couples, or extra characters unless the script clearly introduces them
        - make prompts visually rich and cinematic for vertical videos
        - narration must remain concise and aligned with the script
        - each scene must feel like the next chronological beat of the same story
        """
        response = generate_text(prompt)
        scenes = self._parse_json_array(response)
        normalized = []
        for index, scene in enumerate(scenes or [], start=1):
            if not isinstance(scene, dict):
                continue
            narration = self._clean_text(scene.get("narration", ""))
            image_prompt = self._clean_text(scene.get("image_prompt", ""))
            if not narration or not image_prompt:
                continue
            normalized.append(
                {
                    "scene_number": int(scene.get("scene_number", index)),
                    "purpose": self._clean_text(scene.get("purpose", "scene")),
                    "narration": narration,
                    "image_prompt": image_prompt,
                }
            )
        return normalized[:scene_count]

    def _infer_requested_scene_count(self, text: str) -> int | None:
        raw_text = str(text or "")
        if not raw_text:
            return None
        match = re.search(r"(\d{1,2})\s*(?:partes|parts|scenes|cenas|beats)", raw_text, re.IGNORECASE)
        if not match:
            return None
        try:
            return max(3, int(match.group(1)))
        except Exception:
            return None

    def _clean_text(self, value) -> str:
        text = str(value or "")
        text = text.replace("```json", "").replace("```", "")
        text = re.sub(r"(?m)^\s*\d+[\).:-]?\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_json_snippet(self, response: str) -> str:
        text = str(response or "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start_object = text.find("{")
        start_array = text.find("[")

        starts = [index for index in [start_object, start_array] if index >= 0]
        if not starts:
            return text
        start = min(starts)

        end_object = text.rfind("}")
        end_array = text.rfind("]")
        end = max(end_object, end_array)
        if end >= start:
            return text[start:end + 1]
        return text[start:]

    def _parse_json_object(self, response: str) -> dict:
        snippet = self._extract_json_snippet(response)
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _parse_json_array(self, response: str) -> list:
        snippet = self._extract_json_snippet(response)
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
