# Narrative Modes

MoneyPrinter supports multiple YouTube creation modes for more coherent scene planning.

## Menu organization

Inside the YouTube workspace, the categories are now grouped under `Create Videos` and `Generate Topics and Insights` instead of being scattered in the main menu.

## Modes

- `classic`: regular short generation using automatic prompts
- `story`: scene-based storytelling or comedy
- `finance`: structured market and business commentary
- `biblical`: devotional and biblical reflection format

## What narrative modes generate

Narrative modes create:
- a subject
- a short script
- a `visual_bible.json`
- a `scenes.json`
- scene-by-scene image prompts with continuity

## Config

Example configuration in `config.json`:

```json
{
  "image_generation": {
    "provider": "gemini",
    "consistency_level": "high",
    "use_reference_images": false,
    "gemini_api_base_url": "https://generativelanguage.googleapis.com/v1beta",
    "gemini_api_key": "",
    "gemini_model": "gemini-3.1-flash-image-preview",
    "aspect_ratio": "9:16"
  },
  "storytelling": {
    "default_scene_count": 6,
    "character_persistence": true,
    "visual_bible_enabled": true
  }
}
```

## Optional scene video generation

The current build also supports optional scene video generation configuration.

Example:

```json
{
  "video_generation": {
    "enabled": false,
    "provider": "none",
    "mode": "hybrid",
    "generate_first_n_scenes": 1,
    "duration_seconds": 6,
    "resolution": "1080P",
    "poll_interval_seconds": 10,
    "poll_timeout_seconds": 900,
    "minimax_api_key": "",
    "minimax_base_url": "https://api.minimax.io/v1",
    "minimax_model": "MiniMax-Hailuo-2.3",
    "gemini_api_key": "",
    "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta",
    "gemini_model": "veo-3.1-generate-preview"
  }
}
```

Modes:
- `none`: disabled
- `hybrid`: try generating scene videos for the first N scenes and fall back to images if a clip fails
- `video_only`: require video generation for configured scenes

## Notes about providers

The current build directly supports:
- Gemini image generation
- MiniMax text-to-video polling flow
- Gemini/Veo long-running video generation polling flow

The provider abstraction allows additional services to be integrated later without changing the main creation flow.
