import asyncio
import os
import soundfile as sf
from kittentts import KittenTTS as KittenModel

from config import ROOT_DIR, get_tts_config
from status import warning

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000


class TTS:
    def __init__(self) -> None:
        self._model = None
        self._config = get_tts_config()

    def _normalize_language(self, language: str | None) -> str:
        normalized = str(language or self._config.get("default_language", "english")).strip().lower()
        if normalized in {"pt", "pt-br", "portuguese", "portugues", "português", "br", "brazilian portuguese"}:
            return "portuguese"
        return "english"

    def list_voice_options(self, language: str | None = None) -> list[dict]:
        normalized_language = self._normalize_language(language)
        profile = self._config.get("language_profiles", {}).get(normalized_language, {})
        variants = profile.get("variants", {}) if isinstance(profile.get("variants", {}), dict) else {}
        default_variant = str(profile.get("default_variant", "default")).strip().lower() or "default"

        options = []
        for variant_key, variant in variants.items():
            if not isinstance(variant, dict):
                continue
            options.append(
                {
                    "key": str(variant_key).strip().lower(),
                    "label": str(variant.get("label", variant_key)).strip() or str(variant_key),
                    "provider": str(variant.get("provider", profile.get("provider", self._config.get("default_provider", "edge")))).strip().lower() or "edge",
                    "voice": str(variant.get("voice", profile.get("voice", self._config.get("legacy_voice", "Jasper")))).strip() or self._config.get("legacy_voice", "Jasper"),
                    "is_default": str(variant_key).strip().lower() == default_variant,
                }
            )
        return options

    def _get_profile(
        self,
        language: str | None = None,
        provider: str | None = None,
        voice: str | None = None,
        variant: str | None = None,
    ) -> dict:
        normalized_language = self._normalize_language(language)
        profiles = self._config.get("language_profiles", {})
        base_profile = profiles.get(normalized_language, {})
        variants = base_profile.get("variants", {}) if isinstance(base_profile.get("variants", {}), dict) else {}
        variant_key = str(variant or base_profile.get("default_variant", "default")).strip().lower() or "default"
        selected_variant = variants.get(variant_key, {}) if isinstance(variants.get(variant_key, {}), dict) else {}

        resolved_provider = str(
            provider
            or selected_variant.get("provider")
            or base_profile.get("provider")
            or self._config.get("default_provider", "edge")
        ).strip().lower()
        resolved_voice = str(
            voice
            or selected_variant.get("voice")
            or base_profile.get("voice")
            or self._config.get("legacy_voice", "Jasper")
        ).strip()
        resolved_label = str(
            selected_variant.get("label")
            or variant_key.title()
            or "Default"
        ).strip()

        return {
            "language": normalized_language,
            "provider": resolved_provider or "edge",
            "voice": resolved_voice or self._config.get("legacy_voice", "Jasper"),
            "variant": variant_key,
            "label": resolved_label or "Default",
        }

    def get_output_extension(
        self,
        language: str | None = None,
        provider: str | None = None,
        variant: str | None = None,
        voice: str | None = None,
    ) -> str:
        profile = self._get_profile(language=language, provider=provider, variant=variant, voice=voice)
        return ".mp3" if profile["provider"] == "edge" else ".wav"

    def _ensure_kitten_model(self) -> KittenModel:
        if self._model is None:
            self._model = KittenModel(KITTEN_MODEL)
        return self._model

    def _synthesize_kitten(self, text: str, output_file: str, voice: str) -> str:
        model = self._ensure_kitten_model()
        audio = model.generate(text, voice=voice)
        sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        return output_file

    def _synthesize_edge(self, text: str, output_file: str, voice: str) -> str:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Install dependencies again to enable language-aware neural voices."
            ) from exc

        async def _run() -> None:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(output_file)

        asyncio.run(_run())
        return output_file

    def synthesize(
        self,
        text,
        output_file=None,
        language: str | None = None,
        provider: str | None = None,
        voice: str | None = None,
        variant: str | None = None,
    ):
        profile = self._get_profile(language=language, provider=provider, voice=voice, variant=variant)
        final_output = output_file or os.path.join(ROOT_DIR, ".mp", "audio" + self.get_output_extension(language, provider, variant, voice))

        if profile["provider"] == "edge":
            try:
                return self._synthesize_edge(text, final_output, profile["voice"])
            except Exception as exc:
                warning(f"Falling back to KittenTTS after edge-tts failure: {exc}")
                fallback_voice = self._config.get("legacy_voice", "Jasper")
                fallback_output = os.path.splitext(final_output)[0] + ".wav"
                return self._synthesize_kitten(text, fallback_output, fallback_voice)

        return self._synthesize_kitten(text, final_output, profile["voice"])
