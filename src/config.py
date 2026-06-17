import json
import os
import sys
from functools import lru_cache

import srt_equalizer
from termcolor import colored

ROOT_DIR = os.path.dirname(sys.path[0])


def get_config_path() -> str:
    """
    Gets the config.json path.

    Returns:
        path (str): Absolute config path
    """
    return os.path.join(ROOT_DIR, "config.json")


@lru_cache(maxsize=16)
def _load_config_cached(config_path: str, config_mtime: float | None) -> dict:
    if config_mtime is None or not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as file:
        parsed = json.load(file)

    if parsed is None:
        return {}

    return parsed


def load_config() -> dict:
    """
    Loads config.json and automatically refreshes the cache when the file changes.

    Returns:
        config (dict): Parsed configuration dictionary.
    """
    config_path = get_config_path()
    config_mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else None
    return _load_config_cached(config_path, config_mtime)


def clear_config_cache() -> None:
    """
    Clears the cached config.json contents.

    Returns:
        None
    """
    _load_config_cached.cache_clear()


def _get_config_value(key: str, default=None):
    return load_config().get(key, default)


def assert_folder_structure() -> None:
    """
    Make sure that the nessecary folder structure is present.

    Returns:
        None
    """
    if not os.path.exists(os.path.join(ROOT_DIR, ".mp")):
        if get_verbose():
            print(
                colored(
                    f"=> Creating .mp folder at {os.path.join(ROOT_DIR, '.mp')}",
                    "green",
                )
            )
        os.makedirs(os.path.join(ROOT_DIR, ".mp"))


def get_first_time_running() -> bool:
    """
    Checks if the program is running for the first time by checking if .mp folder exists.

    Returns:
        exists (bool): True if the program is running for the first time, False otherwise
    """
    return not os.path.exists(os.path.join(ROOT_DIR, ".mp"))


def get_email_credentials() -> dict:
    """
    Gets the email credentials from the config file.

    Returns:
        credentials (dict): The email credentials
    """
    return _get_config_value("email", {})


def get_verbose() -> bool:
    """
    Gets the verbose flag from the config file.

    Returns:
        verbose (bool): The verbose flag
    """
    return bool(_get_config_value("verbose", False))


def get_firefox_profile_path() -> str:
    """
    Gets the path to the Firefox profile.

    Returns:
        path (str): The path to the Firefox profile
    """
    return str(_get_config_value("firefox_profile", ""))


def get_headless() -> bool:
    """
    Gets the headless flag from the config file.

    Returns:
        headless (bool): The headless flag
    """
    return bool(_get_config_value("headless", False))


def get_ollama_base_url() -> str:
    """
    Gets the Ollama base URL.

    Returns:
        url (str): The Ollama base URL
    """
    return str(_get_config_value("ollama_base_url", "http://127.0.0.1:11434"))


def get_ollama_model() -> str:
    """
    Gets the Ollama model name from the config file.

    Returns:
        model (str): The Ollama model name, or empty string if not set.
    """
    return str(_get_config_value("ollama_model", ""))


def get_twitter_language() -> str:
    """
    Gets the Twitter language from the config file.

    Returns:
        language (str): The Twitter language
    """
    return str(_get_config_value("twitter_language", "English"))


def get_nanobanana2_api_base_url() -> str:
    """
    Gets the Nano Banana 2 (Gemini image) API base URL.

    Returns:
        url (str): API base URL
    """
    return str(
        _get_config_value(
            "nanobanana2_api_base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        )
    )


def get_nanobanana2_api_key() -> str:
    """
    Gets the Nano Banana 2 API key.

    Returns:
        key (str): API key
    """
    configured = str(_get_config_value("nanobanana2_api_key", "")).strip()
    return configured or os.environ.get("GEMINI_API_KEY", "")


def get_nanobanana2_model() -> str:
    """
    Gets the Nano Banana 2 model name.

    Returns:
        model (str): Model name
    """
    return str(_get_config_value("nanobanana2_model", "gemini-3.1-flash-image-preview"))


def get_nanobanana2_aspect_ratio() -> str:
    """
    Gets the aspect ratio for Nano Banana 2 image generation.

    Returns:
        ratio (str): Aspect ratio
    """
    return str(_get_config_value("nanobanana2_aspect_ratio", "9:16"))


def get_image_generation_config() -> dict:
    """
    Gets the image generation configuration with safe defaults.

    Returns:
        config (dict): Image generation settings
    """
    raw_config = _get_config_value("image_generation", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    return {
        "provider": str(raw_config.get("provider", "gemini")).strip().lower() or "gemini",
        "consistency_level": str(raw_config.get("consistency_level", "high")).strip().lower() or "high",
        "use_reference_images": bool(raw_config.get("use_reference_images", False)),
        "gemini_api_base_url": str(raw_config.get("gemini_api_base_url", get_nanobanana2_api_base_url())).strip(),
        "gemini_api_key": str(raw_config.get("gemini_api_key", get_nanobanana2_api_key())).strip(),
        "gemini_model": str(raw_config.get("gemini_model", get_nanobanana2_model())).strip(),
        "aspect_ratio": str(raw_config.get("aspect_ratio", get_nanobanana2_aspect_ratio())).strip(),
    }


def get_threads() -> int:
    """
    Gets the amount of threads to use for example when writing to a file with MoviePy.

    Returns:
        threads (int): Amount of threads
    """
    return int(_get_config_value("threads", 2))


def get_zip_url() -> str:
    """
    Gets the URL to the zip file containing the songs.

    Returns:
        url (str): The URL to the zip file
    """
    return str(_get_config_value("zip_url", ""))


def get_is_for_kids() -> bool:
    """
    Gets the is for kids flag from the config file.

    Returns:
        is_for_kids (bool): The is for kids flag
    """
    return bool(_get_config_value("is_for_kids", False))


def get_google_maps_scraper_zip_url() -> str:
    """
    Gets the URL to the zip file containing the Google Maps scraper.

    Returns:
        url (str): The URL to the zip file
    """
    return str(_get_config_value("google_maps_scraper", ""))


def get_google_maps_scraper_niche() -> str:
    """
    Gets the niche for the Google Maps scraper.

    Returns:
        niche (str): The niche
    """
    return str(_get_config_value("google_maps_scraper_niche", ""))


def get_scraper_timeout() -> int:
    """
    Gets the timeout for the scraper.

    Returns:
        timeout (int): The timeout
    """
    configured = _get_config_value("scraper_timeout", 300)
    return int(configured or 300)


def get_outreach_message_subject() -> str:
    """
    Gets the outreach message subject.

    Returns:
        subject (str): The outreach message subject
    """
    return str(_get_config_value("outreach_message_subject", "I have a question..."))


def get_outreach_message_body_file() -> str:
    """
    Gets the outreach message body file.

    Returns:
        file (str): The outreach message body file
    """
    return str(_get_config_value("outreach_message_body_file", "outreach_message.html"))


def get_tts_voice() -> str:
    """
    Gets the TTS voice from the config file.

    Returns:
        voice (str): The TTS voice
    """
    return str(_get_config_value("tts_voice", "Jasper"))


def get_assemblyai_api_key() -> str:
    """
    Gets the AssemblyAI API key.

    Returns:
        key (str): The AssemblyAI API key
    """
    return str(_get_config_value("assembly_ai_api_key", ""))


def get_stt_provider() -> str:
    """
    Gets the configured STT provider.

    Returns:
        provider (str): The STT provider
    """
    return str(_get_config_value("stt_provider", "local_whisper"))


def get_whisper_model() -> str:
    """
    Gets the local Whisper model name.

    Returns:
        model (str): Whisper model name
    """
    return str(_get_config_value("whisper_model", "base"))


def get_whisper_device() -> str:
    """
    Gets the target device for Whisper inference.

    Returns:
        device (str): Whisper device
    """
    return str(_get_config_value("whisper_device", "auto"))


def get_whisper_compute_type() -> str:
    """
    Gets the compute type for Whisper inference.

    Returns:
        compute_type (str): Whisper compute type
    """
    return str(_get_config_value("whisper_compute_type", "int8"))


def equalize_subtitles(srt_path: str, max_chars: int = 10) -> None:
    """
    Equalizes the subtitles in a SRT file.

    Args:
        srt_path (str): The path to the SRT file
        max_chars (int): The maximum amount of characters in a subtitle

    Returns:
        None
    """
    srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)


def get_font() -> str:
    """
    Gets the font from the config file.

    Returns:
        font (str): The font
    """
    return str(_get_config_value("font", "bold_font.ttf"))


def get_fonts_dir() -> str:
    """
    Gets the fonts directory.

    Returns:
        dir (str): The fonts directory
    """
    return os.path.join(ROOT_DIR, "fonts")


def get_imagemagick_path() -> str:
    """
    Gets the path to ImageMagick.

    Returns:
        path (str): The path to ImageMagick
    """
    return str(_get_config_value("imagemagick_path", ""))


def get_script_sentence_length() -> int:
    """
    Gets the forced script's sentence length.
    In case there is no sentence length in config, returns 4 when none

    Returns:
        length (int): Length of script's sentence
    """
    configured = load_config().get("script_sentence_length")
    return int(configured) if configured is not None else 4


def get_storytelling_config() -> dict:
    """
    Gets narrative storytelling defaults.

    Returns:
        config (dict): Storytelling settings
    """
    raw_config = _get_config_value("storytelling", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    return {
        "default_scene_count": max(3, int(raw_config.get("default_scene_count", 6))),
        "character_persistence": bool(raw_config.get("character_persistence", True)),
        "visual_bible_enabled": bool(raw_config.get("visual_bible_enabled", True)),
    }


def get_video_generation_config() -> dict:
    """
    Gets the optional scene video generation configuration.

    Returns:
        config (dict): Video generation settings
    """
    raw_config = _get_config_value("video_generation", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    return {
        "enabled": bool(raw_config.get("enabled", False)),
        "provider": str(raw_config.get("provider", "none")).strip().lower() or "none",
        "mode": str(raw_config.get("mode", "hybrid")).strip().lower() or "hybrid",
        "generate_first_n_scenes": max(0, int(raw_config.get("generate_first_n_scenes", 0))),
        "duration_seconds": max(1, int(raw_config.get("duration_seconds", 6))),
        "resolution": str(raw_config.get("resolution", "1080P")).strip() or "1080P",
        "poll_interval_seconds": max(1, int(raw_config.get("poll_interval_seconds", 10))),
        "poll_timeout_seconds": max(30, int(raw_config.get("poll_timeout_seconds", 900))),
        "minimax_api_key": str(raw_config.get("minimax_api_key", "")).strip(),
        "minimax_base_url": str(raw_config.get("minimax_base_url", "https://api.minimax.io/v1")).strip(),
        "minimax_model": str(raw_config.get("minimax_model", "MiniMax-Hailuo-2.3")).strip(),
        "gemini_api_key": str(raw_config.get("gemini_api_key", get_image_generation_config().get("gemini_api_key", ""))).strip(),
        "gemini_base_url": str(raw_config.get("gemini_base_url", "https://generativelanguage.googleapis.com/v1beta")).strip(),
        "gemini_model": str(raw_config.get("gemini_model", "veo-3.1-generate-preview")).strip(),
    }


def get_post_bridge_config() -> dict:
    """
    Gets the Post Bridge configuration with safe defaults.

    Returns:
        config (dict): Sanitized Post Bridge configuration
    """
    defaults = {
        "enabled": False,
        "api_key": "",
        "platforms": ["tiktok", "instagram"],
        "account_ids": [],
        "auto_crosspost": False,
    }
    supported_platforms = {"tiktok", "instagram"}

    raw_config = load_config().get("post_bridge", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    raw_platforms = raw_config.get("platforms")
    normalized_platforms = []
    seen_platforms = set()

    if raw_platforms is None:
        normalized_platforms = defaults["platforms"].copy()
    elif isinstance(raw_platforms, list):
        for platform in raw_platforms:
            normalized_platform = str(platform).strip().lower()
            if (
                normalized_platform in supported_platforms
                and normalized_platform not in seen_platforms
            ):
                normalized_platforms.append(normalized_platform)
                seen_platforms.add(normalized_platform)
    else:
        normalized_platforms = []

    raw_account_ids = raw_config.get("account_ids", defaults["account_ids"])
    normalized_account_ids = []
    if isinstance(raw_account_ids, list):
        for account_id in raw_account_ids:
            try:
                normalized_account_ids.append(int(account_id))
            except (TypeError, ValueError):
                continue

    api_key = str(raw_config.get("api_key", "")).strip()
    if not api_key:
        api_key = os.environ.get("POST_BRIDGE_API_KEY", "").strip()

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "api_key": api_key,
        "platforms": normalized_platforms,
        "account_ids": normalized_account_ids,
        "auto_crosspost": bool(
            raw_config.get("auto_crosspost", defaults["auto_crosspost"])
        ),
    }


def get_automation_config() -> dict:
    """
    Gets the automation scheduler configuration with safe defaults.

    Returns:
        config (dict): Sanitized automation configuration
    """
    defaults = {
        "enabled": False,
        "timezone": "America/Sao_Paulo",
        "jobs": [],
    }

    raw_config = load_config().get("automation", {})
    if not isinstance(raw_config, dict):
        raw_config = {}

    raw_jobs = raw_config.get("jobs", [])
    normalized_jobs = []

    if isinstance(raw_jobs, list):
        for index, raw_job in enumerate(raw_jobs, start=1):
            if not isinstance(raw_job, dict):
                continue

            topics = raw_job.get("topics", [])
            news_sources = raw_job.get("news_sources", [])
            news_blacklist = raw_job.get("news_blacklist", [])
            normalized_jobs.append(
                {
                    "id": str(raw_job.get("id") or f"job-{index}").strip(),
                    "enabled": bool(raw_job.get("enabled", True)),
                    "platform": str(raw_job.get("platform", "youtube")).strip().lower(),
                    "account_id": str(raw_job.get("account_id", "")).strip(),
                    "create_cron": str(raw_job.get("create_cron", "")).strip(),
                    "publish_cron": str(raw_job.get("publish_cron", "")).strip(),
                    "topic_mode": str(raw_job.get("topic_mode", "scheduled")).strip().lower(),
                    "topics": [str(topic).strip() for topic in topics if str(topic).strip()] if isinstance(topics, list) else [],
                    "news_sources": [str(source).strip() for source in news_sources if str(source).strip()] if isinstance(news_sources, list) else [],
                    "news_blacklist": [str(term).strip().lower() for term in news_blacklist if str(term).strip()] if isinstance(news_blacklist, list) else [],
                    "news_max_age_hours": max(1, int(raw_job.get("news_max_age_hours", 72))),
                    "news_title_keyword_weight": max(0, int(raw_job.get("news_title_keyword_weight", 5))),
                    "news_summary_keyword_weight": max(0, int(raw_job.get("news_summary_keyword_weight", 2))),
                    "news_recency_weight": max(0, int(raw_job.get("news_recency_weight", 1))),
                    "max_per_day": max(1, int(raw_job.get("max_per_day", 1))),
                }
            )

    return {
        "enabled": bool(raw_config.get("enabled", defaults["enabled"])),
        "timezone": str(raw_config.get("timezone", defaults["timezone"])).strip() or defaults["timezone"],
        "jobs": normalized_jobs,
    }
