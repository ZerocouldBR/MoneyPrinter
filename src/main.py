import json
import os
import sys
import schedule
import subprocess

from art import *
from cache import *
from utils import *
from config import *
from status import *
from uuid import uuid4
from constants import *
from classes.Tts import TTS
from termcolor import colored
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from prettytable import PrettyTable
from classes.Outreach import Outreach
from classes.AFM import AffiliateMarketing
from llm_provider import list_models, select_model, get_active_model, generate_text
from post_bridge_integration import maybe_crosspost_youtube_short
from cached_image_workflow import (
    generate_video_reusing_cached_images,
    generate_video_with_image_preservation,
)
from image_library import recover_image_library, list_image_library_projects
from services.narrative_mode_service import NarrativeModeService


def ask_yes_no(prompt: str) -> bool:
    while True:
        response = question(prompt).strip().lower()
        if response in {"yes", "y", "sim", "s", "1"}:
            return True
        if response in {"no", "n", "nao", "não", "0"}:
            return False
        warning("Please answer with Yes/No, Y/N, Sim/Não, or 1/0.")



def normalize_video_language(value: str | None, fallback: str = "English") -> str:
    normalized = str(value or fallback).strip().lower()
    if normalized in {"2", "pt", "pt-br", "portuguese", "portugues", "português", "br"}:
        return "Portuguese"
    return "English"



def ask_video_language(default_language: str) -> str:
    info(f"Default account language: {default_language}", False)
    info("Choose the video language for this creation:", False)
    print(colored(" 1. Use account default", "cyan"))
    print(colored(" 2. English", "cyan"))
    print(colored(" 3. Portuguese", "cyan"))

    while True:
        raw = question("Language option (ENTER = account default): ").strip().lower()
        if raw in {"", "1", "default", "padrao", "padrão"}:
            return normalize_video_language(default_language, default_language)
        if raw in {"2", "en", "english", "ingles", "inglês"}:
            return "English"
        if raw in {"3", "pt", "pt-br", "portuguese", "portugues", "português"}:
            return "Portuguese"
        warning("Choose 1, 2, or 3.")



def _language_profile_key(language: str) -> str:
    normalized = str(language or "english").strip().lower()
    if normalized.startswith("portugu") or normalized in {"pt", "pt-br", "br"}:
        return "portuguese"
    return "english"



def get_channel_default_voice_option(account: dict, tts: TTS, selected_language: str) -> dict | None:
    options = tts.list_voice_options(selected_language)
    if not options:
        return None

    tts_defaults = account.get("tts_defaults", {}) if isinstance(account.get("tts_defaults", {}), dict) else {}
    language_key = _language_profile_key(selected_language)
    preferred = tts_defaults.get(language_key, {}) if isinstance(tts_defaults.get(language_key, {}), dict) else {}
    preferred_variant = str(preferred.get("variant", "")).strip().lower()

    if preferred_variant:
        for option in options:
            if option.get("key") == preferred_variant:
                return option

    for option in options:
        if option.get("is_default"):
            return option
    return options[0]



def save_channel_default_voice(account: dict, youtube: YouTube, selected_language: str, selected_voice: dict | None) -> None:
    if not selected_voice:
        return

    language_key = _language_profile_key(selected_language)
    current_defaults = account.get("tts_defaults", {}) if isinstance(account.get("tts_defaults", {}), dict) else {}
    current_defaults[language_key] = {
        "variant": selected_voice.get("key"),
        "voice": selected_voice.get("voice"),
        "provider": selected_voice.get("provider"),
        "label": selected_voice.get("label"),
    }
    account["tts_defaults"] = current_defaults
    youtube.set_channel_tts_defaults(current_defaults)
    update_account("youtube", account["id"], {"tts_defaults": current_defaults})



def ask_voice_profile(tts: TTS, selected_language: str, default_option: dict | None = None) -> dict | None:
    options = tts.list_voice_options(selected_language)
    if not options:
        return None

    default_key = str((default_option or {}).get("key", "")).strip().lower()

    info(f"Choose the narrator voice for {selected_language}:", False)
    for idx, option in enumerate(options, start=1):
        suffix = " (channel default)" if option.get("key") == default_key else ""
        print(colored(f" {idx}. {option.get('label', option.get('key', 'Voice'))}{suffix}", "cyan"))

    while True:
        raw = question("Voice option (ENTER = channel default): ").strip().lower()
        if raw == "":
            if default_option:
                return default_option
            for option in options:
                if option.get("is_default"):
                    return option
            return options[0]
        try:
            index = int(raw) - 1
            if 0 <= index < len(options):
                return options[index]
        except ValueError:
            pass
        warning("Choose one of the listed voice numbers.")



def maybe_upload_youtube_short(youtube: YouTube) -> None:
    if ask_yes_no("Do you want to upload this video to YouTube? (Yes/No): "):
        upload_success = youtube.upload_video()
        if upload_success:
            maybe_crosspost_youtube_short(
                video_path=youtube.video_path,
                title=youtube.metadata.get("title", ""),
                interactive=True,
            )
        else:
            warning("YouTube upload failed. Skipping Post Bridge cross-post.")


def prompt_youtube_generation_inputs(allow_script_without_topic: bool = False) -> tuple[str | None, str | None]:
    info("Press ENTER to use automatic topic/script generation.", False)
    custom_topic = question("Optional custom topic: ").strip()

    if not custom_topic and not allow_script_without_topic:
        return None, None

    if not ask_yes_no("Do you want to provide your own full script? (Yes/No): "):
        return custom_topic or None, None

    info(
        "Paste your script below. Finish with a single line containing only END.",
        False,
    )
    lines = []
    while True:
        line = input().rstrip("\n")
        if line.strip() == "END":
            break
        lines.append(line)

    custom_script = "\n".join(lines).strip()
    return custom_topic or None, custom_script or None



def ask_narrative_scene_count(mode: str, long_form: bool = False) -> tuple[int | None, str]:
    labels = {
        "story": "Story runtime profile",
        "finance": "Finance runtime profile",
        "biblical": "Biblical runtime profile",
    }
    info(labels.get(mode, "Narrative runtime profile"), False)

    if not long_form:
        print(colored(" 1. Fast short (6 scenes)", "cyan"))
        print(colored(" 2. Rich short (10 scenes)", "cyan"))
        print(colored(" 3. Extended video (16 scenes, about 1 to 3 min)", "cyan"))
        print(colored(" 4. Long-form segment (30 scenes, about 3 to 5 min)", "cyan"))
        print(colored(" 5. Custom scene count", "cyan"))
        print(colored(" 6. Auto from prompt/profile", "cyan"))

        while True:
            raw = question("Runtime option (ENTER = auto): ").strip().lower()
            if raw in {"", "6", "auto"}:
                return None, "auto"
            if raw == "1":
                return 6, "fast-short"
            if raw == "2":
                return 10, "rich-short"
            if raw == "3":
                return 16, "extended"
            if raw == "4":
                return 30, "long-form"
            if raw == "5":
                custom_raw = question("Enter the number of scenes/parts: ").strip()
                try:
                    value = max(3, min(120, int(custom_raw)))
                    return value, f"custom-{value}"
                except ValueError:
                    warning("Enter a valid number of scenes.")
                    continue
            warning("Choose 1, 2, 3, 4, 5, or 6.")

    print(colored(" 1. Long-form segment (30 scenes, about 3 to 5 min)", "cyan"))
    print(colored(" 2. Deep long-form (60 scenes, about 8 to 12 min)", "cyan"))
    print(colored(" 3. Extended long-form (90 scenes, about 15 to 20 min)", "cyan"))
    print(colored(" 4. Feature draft (120 scenes, about 25 to 35 min)", "cyan"))
    print(colored(" 5. Custom scene count", "cyan"))

    while True:
        raw = question("Long-form option: ").strip().lower()
        if raw == "1":
            return 30, "long-form-30"
        if raw == "2":
            return 60, "long-form-60"
        if raw == "3":
            return 90, "long-form-90"
        if raw == "4":
            return 120, "feature-120"
        if raw == "5":
            custom_raw = question("Enter the number of scenes/parts: ").strip()
            try:
                value = max(30, min(240, int(custom_raw)))
                return value, f"custom-{value}"
            except ValueError:
                warning("Enter a valid number of scenes.")
                continue
        warning("Choose 1, 2, 3, 4, or 5.")


def generate_youtube_short(youtube: YouTube, tts: TTS, account: dict) -> None:
    selected_language = ask_video_language(youtube.account_language)
    youtube.set_generation_language(selected_language)
    selected_voice = ask_voice_profile(
        tts,
        selected_language,
        get_channel_default_voice_option(account, tts, selected_language),
    )
    youtube.set_generation_voice(
        voice=(selected_voice or {}).get("voice"),
        provider=(selected_voice or {}).get("provider"),
        variant=(selected_voice or {}).get("key"),
        label=(selected_voice or {}).get("label"),
    )
    save_channel_default_voice(account, youtube, selected_language, selected_voice)
    custom_topic, custom_script = prompt_youtube_generation_inputs()
    generated_path = generate_video_with_image_preservation(
        youtube,
        tts,
        topic=custom_topic,
        script_override=custom_script,
        content_mode="classic",
    )
    success(f'Generated local video at "{generated_path}"')
    exported_video_path = getattr(youtube, "exported_video_path", None)
    exported_video_dir = getattr(youtube, "exported_video_dir", None)
    if exported_video_path:
        success(f'Persistent exported copy: "{exported_video_path}"')
    if exported_video_dir:
        success(f'Video project folder: "{exported_video_dir}"')


def _apply_generation_language_and_voice(youtube: YouTube, tts: TTS, account: dict) -> None:
    selected_language = ask_video_language(youtube.account_language)
    youtube.set_generation_language(selected_language)
    selected_voice = ask_voice_profile(
        tts,
        selected_language,
        get_channel_default_voice_option(account, tts, selected_language),
    )
    youtube.set_generation_voice(
        voice=(selected_voice or {}).get("voice"),
        provider=(selected_voice or {}).get("provider"),
        variant=(selected_voice or {}).get("key"),
        label=(selected_voice or {}).get("label"),
    )
    save_channel_default_voice(account, youtube, selected_language, selected_voice)



def generate_youtube_narrative_short(youtube: YouTube, tts: TTS, account: dict, mode: str) -> None:
    _apply_generation_language_and_voice(youtube, tts, account)
    requested_scene_count, runtime_profile = ask_narrative_scene_count(mode)
    custom_topic, custom_script = prompt_youtube_generation_inputs()
    planner = NarrativeModeService()
    plan = planner.build_plan(
        mode=mode,
        niche=f"{youtube.niche}. {youtube.content_brief}".strip(),
        language=youtube.language,
        topic_override=custom_topic,
        script_override=custom_script,
        scene_count_override=requested_scene_count,
    )
    info(f"Narrative mode selected: {plan['mode_label']} | runtime: {runtime_profile} | scenes: {plan.get('scene_count', len(plan.get('scenes', [])))}", False)
    generated_path = generate_video_with_image_preservation(
        youtube,
        tts,
        topic=plan.get("subject"),
        script_override=plan.get("script"),
        scene_plan=plan.get("scenes"),
        visual_bible=plan.get("visual_bible"),
        content_mode=plan.get("mode", mode),
    )
    success(f'Generated local video at "{generated_path}"')
    exported_video_path = getattr(youtube, "exported_video_path", None)
    exported_video_dir = getattr(youtube, "exported_video_dir", None)
    if exported_video_path:
        success(f'Persistent exported copy: "{exported_video_path}"')
    if exported_video_dir:
        success(f'Video project folder: "{exported_video_dir}"')



def generate_youtube_long_form_story(youtube: YouTube, tts: TTS, account: dict) -> None:
    _apply_generation_language_and_voice(youtube, tts, account)
    requested_scene_count, runtime_profile = ask_narrative_scene_count("story", long_form=True)
    custom_topic, custom_script = prompt_youtube_generation_inputs(allow_script_without_topic=True)
    planner = NarrativeModeService()
    plan = planner.build_plan(
        mode="story",
        niche=f"{youtube.niche}. {youtube.content_brief}".strip(),
        language=youtube.language,
        topic_override=custom_topic,
        script_override=custom_script,
        scene_count_override=requested_scene_count,
    )
    info(
        f"Long-form story mode | runtime: {runtime_profile} | scenes: {plan.get('scene_count', len(plan.get('scenes', [])))}",
        False,
    )
    generated_path = generate_video_with_image_preservation(
        youtube,
        tts,
        topic=plan.get("subject"),
        script_override=plan.get("script"),
        scene_plan=plan.get("scenes"),
        visual_bible=plan.get("visual_bible"),
        content_mode="longform_story",
    )
    success(f'Generated local video at "{generated_path}"')
    exported_video_path = getattr(youtube, "exported_video_path", None)
    exported_video_dir = getattr(youtube, "exported_video_dir", None)
    if exported_video_path:
        success(f'Persistent exported copy: "{exported_video_path}"')
    if exported_video_dir:
        success(f'Video project folder: "{exported_video_dir}"')



def generate_youtube_feature_video(youtube: YouTube, tts: TTS, account: dict) -> None:
    _apply_generation_language_and_voice(youtube, tts, account)
    info("Feature / long script mode works best when you already have a full script.", False)
    requested_scene_count, runtime_profile = ask_narrative_scene_count("story", long_form=True)
    custom_topic, custom_script = prompt_youtube_generation_inputs(allow_script_without_topic=True)
    if not custom_script and not ask_yes_no("No full script was provided. Do you want to auto-generate a long draft anyway? (Yes/No): "):
        warning("Feature generation canceled. Provide a script or allow auto-generation.")
        return

    planner = NarrativeModeService()
    plan = planner.build_plan(
        mode="story",
        niche=f"{youtube.niche}. {youtube.content_brief}".strip(),
        language=youtube.language,
        topic_override=custom_topic,
        script_override=custom_script,
        scene_count_override=requested_scene_count,
    )
    info(
        f"Feature / long script mode | runtime: {runtime_profile} | scenes: {plan.get('scene_count', len(plan.get('scenes', [])))}",
        False,
    )
    generated_path = generate_video_with_image_preservation(
        youtube,
        tts,
        topic=plan.get("subject"),
        script_override=plan.get("script"),
        scene_plan=plan.get("scenes"),
        visual_bible=plan.get("visual_bible"),
        content_mode="feature_script",
    )
    success(f'Generated local video at "{generated_path}"')
    exported_video_path = getattr(youtube, "exported_video_path", None)
    exported_video_dir = getattr(youtube, "exported_video_dir", None)
    if exported_video_path:
        success(f'Persistent exported copy: "{exported_video_path}"')
    if exported_video_dir:
        success(f'Video project folder: "{exported_video_dir}"')



def ask_menu_choice(title: str, options: list[str]) -> int:
    while True:
        info(f"\n============ {title.upper()} ============", False)
        for idx, option in enumerate(options, start=1):
            print(colored(f" {idx}. {option}", "cyan"))
        info("=================================\n", False)
        raw = question("Select an option: ").strip()
        try:
            selected = int(raw)
            if 1 <= selected <= len(options):
                return selected
        except ValueError:
            pass
        warning("Invalid option. Please choose one of the listed numbers.")



def build_default_content_profile(account: dict) -> dict:
    return {
        "id": str(uuid4()),
        "name": "Default",
        "niche": str(account.get("niche", "")).strip(),
        "language": normalize_video_language(account.get("language", "English"), "English"),
        "content_brief": "",
        "subject_hints": "",
        "preferred_mode": "classic",
    }



def ensure_youtube_account_profiles(account: dict) -> bool:
    changed = False
    profiles = account.get("content_profiles")
    if not isinstance(profiles, list) or not profiles:
        account["content_profiles"] = [build_default_content_profile(account)]
        changed = True

    normalized_profiles = []
    for profile in account.get("content_profiles", []):
        if not isinstance(profile, dict):
            continue
        normalized_profiles.append(
            {
                "id": str(profile.get("id") or uuid4()),
                "name": str(profile.get("name") or f"Profile {len(normalized_profiles) + 1}").strip(),
                "niche": str(profile.get("niche") or account.get("niche", "")).strip(),
                "language": normalize_video_language(profile.get("language", account.get("language", "English")), "English"),
                "content_brief": str(profile.get("content_brief", "")).strip(),
                "subject_hints": str(profile.get("subject_hints", "")).strip(),
                "preferred_mode": str(profile.get("preferred_mode", "classic")).strip().lower() or "classic",
            }
        )
    if normalized_profiles != account.get("content_profiles"):
        account["content_profiles"] = normalized_profiles
        changed = True

    active_profile_id = str(account.get("active_content_profile_id", "")).strip()
    if not any(profile.get("id") == active_profile_id for profile in account.get("content_profiles", [])):
        account["active_content_profile_id"] = account["content_profiles"][0]["id"]
        changed = True

    if "tts_defaults" not in account or not isinstance(account.get("tts_defaults"), dict):
        account["tts_defaults"] = {}
        changed = True

    return changed



def get_active_content_profile(account: dict) -> dict:
    ensure_youtube_account_profiles(account)
    active_profile_id = str(account.get("active_content_profile_id", "")).strip()
    for profile in account.get("content_profiles", []):
        if str(profile.get("id", "")).strip() == active_profile_id:
            return profile
    return account["content_profiles"][0]



def apply_active_content_profile(account: dict, youtube: YouTube) -> dict:
    active_profile = get_active_content_profile(account)
    youtube.set_content_profile(active_profile)
    return active_profile



def prompt_preferred_mode(default_value: str = "classic") -> str:
    options = ["classic", "story", "finance", "biblical"]
    info(f"Preferred default mode options: {', '.join(options)}", False)
    raw = question(f"Preferred mode (ENTER = {default_value}): ").strip().lower()
    return raw if raw in options else default_value



def prompt_content_profile(profile: dict | None = None) -> dict:
    existing = dict(profile or {})
    name = question(f"Profile name [{existing.get('name', '')}]: ").strip() or existing.get("name", "") or "Profile"
    niche = question(f"Primary niche/subject area [{existing.get('niche', '')}]: ").strip() or existing.get("niche", "")
    language = normalize_video_language(
        question(f"Default language (English/Portuguese) [{existing.get('language', 'English')}]: ").strip() or existing.get("language", "English"),
        existing.get("language", "English"),
    )
    content_brief = question(f"Creative brief / style notes [{existing.get('content_brief', '')}]: ").strip() or existing.get("content_brief", "")
    subject_hints = question(f"Subject examples / topic hints [{existing.get('subject_hints', '')}]: ").strip() or existing.get("subject_hints", "")
    preferred_mode = prompt_preferred_mode(existing.get("preferred_mode", "classic"))
    return {
        "id": str(existing.get("id") or uuid4()),
        "name": name,
        "niche": niche,
        "language": language,
        "content_brief": content_brief,
        "subject_hints": subject_hints,
        "preferred_mode": preferred_mode,
    }



def list_content_profiles(account: dict) -> None:
    active_profile = get_active_content_profile(account)
    table = PrettyTable()
    table.field_names = ["ID", "Name", "Language", "Mode", "Niche", "Active"]
    for idx, profile in enumerate(account.get("content_profiles", []), start=1):
        table.add_row([
            idx,
            profile.get("name", ""),
            profile.get("language", ""),
            profile.get("preferred_mode", "classic"),
            str(profile.get("niche", ""))[:40],
            "yes" if profile.get("id") == active_profile.get("id") else "",
        ])
    print(table)



def manage_youtube_content_profiles(account: dict, youtube: YouTube) -> None:
    while True:
        user_input = ask_menu_choice("Content Profiles", YOUTUBE_PROFILE_OPTIONS)
        ensure_youtube_account_profiles(account)

        if user_input == 1:
            list_content_profiles(account)
        elif user_input == 2:
            new_profile = prompt_content_profile()
            account.setdefault("content_profiles", []).append(new_profile)
            if not str(account.get("active_content_profile_id", "")).strip():
                account["active_content_profile_id"] = new_profile["id"]
            update_account(
                "youtube",
                account["id"],
                {
                    "content_profiles": account.get("content_profiles", []),
                    "active_content_profile_id": account.get("active_content_profile_id"),
                },
            )
            success(f"Created content profile '{new_profile['name']}'.")
        elif user_input == 3:
            list_content_profiles(account)
            selected = question("Enter the profile number to activate: ").strip()
            try:
                index = int(selected) - 1
                profiles = account.get("content_profiles", [])
                if 0 <= index < len(profiles):
                    account["active_content_profile_id"] = profiles[index]["id"]
                    update_account("youtube", account["id"], {"active_content_profile_id": profiles[index]["id"]})
                    apply_active_content_profile(account, youtube)
                    success(f"Activated profile '{profiles[index]['name']}'.")
                else:
                    warning("Invalid profile selection.")
            except ValueError:
                warning("Invalid profile selection.")
        elif user_input == 4:
            list_content_profiles(account)
            selected = question("Enter the profile number to edit: ").strip()
            try:
                index = int(selected) - 1
                profiles = account.get("content_profiles", [])
                if 0 <= index < len(profiles):
                    profiles[index] = prompt_content_profile(profiles[index])
                    update_account("youtube", account["id"], {"content_profiles": profiles})
                    apply_active_content_profile(account, youtube)
                    success(f"Updated profile '{profiles[index]['name']}'.")
                else:
                    warning("Invalid profile selection.")
            except ValueError:
                warning("Invalid profile selection.")
        elif user_input == 5:
            profiles = account.get("content_profiles", [])
            if len(profiles) <= 1:
                warning("You must keep at least one content profile.")
                continue
            list_content_profiles(account)
            selected = question("Enter the profile number to delete: ").strip()
            try:
                index = int(selected) - 1
                if 0 <= index < len(profiles):
                    removed = profiles.pop(index)
                    if account.get("active_content_profile_id") == removed.get("id"):
                        account["active_content_profile_id"] = profiles[0]["id"]
                    update_account(
                        "youtube",
                        account["id"],
                        {
                            "content_profiles": profiles,
                            "active_content_profile_id": account.get("active_content_profile_id"),
                        },
                    )
                    apply_active_content_profile(account, youtube)
                    success(f"Deleted profile '{removed.get('name', '')}'.")
                else:
                    warning("Invalid profile selection.")
            except ValueError:
                warning("Invalid profile selection.")
        else:
            break



def show_uploaded_youtube_shorts(youtube: YouTube) -> None:
    videos = youtube.get_videos()
    if len(videos) > 0:
        videos_table = PrettyTable()
        videos_table.field_names = ["ID", "Date", "Title"]

        for video in videos:
            videos_table.add_row(
                [
                    videos.index(video) + 1,
                    colored(video["date"], "blue"),
                    colored(video["title"][:60] + "...", "green"),
                ]
            )

        print(videos_table)
    else:
        warning("No uploaded shorts found.")



def generate_youtube_insight(youtube: YouTube, mode: str) -> None:
    selected_language = ask_video_language(youtube.account_language)
    youtube.set_generation_language(selected_language)
    custom_topic = question("Optional custom topic/context for the insight: ").strip() or None

    if mode == "classic":
        prompt = f"""
        Generate one high-potential YouTube Shorts idea for this channel.
        Active profile: {youtube.active_profile_name}
        Niche: {youtube.niche}
        Language: {youtube.language}
        Creative brief: {youtube.content_brief or 'none'}
        Subject hints: {youtube.subject_hints or 'none'}
        Optional context: {custom_topic or 'none'}

        Return plain text only with this structure:
        Topic: ...
        Hook: ...
        Angle: ...
        Why it can work: ...
        """
        insight = str(generate_text(prompt)).strip()
        info("\nClassic insight:\n", False)
        print(insight)
        return

    planner = NarrativeModeService()
    plan = planner.build_plan(
        mode=mode,
        niche=f"{youtube.niche}. {youtube.content_brief}".strip(),
        language=youtube.language,
        topic_override=custom_topic,
        script_override=None,
    )

    table = PrettyTable()
    table.field_names = ["Field", "Value"]
    table.add_row(["mode", plan.get("mode_label", mode)])
    table.add_row(["subject", plan.get("subject", "")])
    table.add_row(["script_preview", str(plan.get("script", ""))[:220]])
    table.add_row(["scenes", len(plan.get("scenes", []))])
    print(table)

    scenes = plan.get("scenes", [])
    if scenes:
        scenes_table = PrettyTable()
        scenes_table.field_names = ["Scene", "Purpose", "Narration"]
        for scene in scenes:
            scenes_table.add_row([
                scene.get("scene_number", ""),
                str(scene.get("purpose", ""))[:28],
                str(scene.get("narration", ""))[:72],
            ])
        print(scenes_table)



def show_content_category_guide() -> None:
    table = PrettyTable()
    table.field_names = ["Category", "Best for", "How it should feel"]
    table.add_row(["Classic", "General faceless Shorts", "Fast, clear, broad, image-led"]) 
    table.add_row(["Story / Entertainment", "Retention and repeat viewing", "Hook, escalation, payoff, strong continuity"])
    table.add_row(["Market / Finance", "News, business, market updates", "Specific, timely, sourced, practical"])
    table.add_row(["Biblical / Devotional", "Faith, reflection, encouragement", "Reverent, accurate, calm, scripture-aware"])
    table.add_row(["Long-form Story", "3 to 20+ minute narrative videos", "Sequential, coherent, scene-based, chapter-like flow"])
    table.add_row(["Feature / Long Script", "Large scripts, adaptations, long narrated pieces", "Script-first, sequential, paced by scene weight"])
    print(table)

    info("Category rules:", False)
    print("- Story: use a clear protagonist, one conflict, one payoff.")
    print("- Finance: anchor claims to real events, dates, prices, or sources.")
    print("- Biblical: cite the verse or passage theme, avoid invented quotations.")
    print("- Classic: keep it simple when speed matters more than narrative depth.")
    print("- Long-form Story: choose enough scenes to preserve continuity and let suspense build gradually.")
    print("- Feature / Long Script: works best when you paste a full script and choose a large scene count.")



def show_real_video_production_guide() -> None:
    info("\nREAL VIDEO PRODUCTION GUIDE", False)
    print("1. Start with a subject that can be verified in the real world.")
    print("2. Keep the hook inside the first 1 to 2 seconds.")
    print("3. Use real references in references.txt, especially for finance and news.")
    print("4. For finance videos, include date context and avoid unverifiable promises.")
    print("5. For biblical videos, base the message on a real passage and keep the tone reverent.")
    print("6. Review scenes.json before upload if the topic is sensitive or factual.")
    print("7. Confirm that video.mp4 exists in outputs/youtube/<project>/ before uploading.")
    print("8. Keep generated assets, script, prompts, and references together for auditability.")
    print("9. If you are using scene video generation, start with only the first scene in video mode.")
    print("10. Upload only after watching the final mp4 locally from start to finish.")



def upload_current_youtube_video(youtube: YouTube) -> None:
    if not getattr(youtube, "video_path", None):
        warning("No current generated video is loaded in memory. Generate a video first in this session.")
        return
    if not os.path.exists(youtube.video_path):
        warning(f"Current generated video was not found: {youtube.video_path}")
        return
    maybe_upload_youtube_short(youtube)



def review_generated_projects_menu(youtube: YouTube) -> None:
    while True:
        user_input = ask_menu_choice("Review Projects", YOUTUBE_REVIEW_OPTIONS)
        if user_input == 1:
            list_generated_projects()
        elif user_input == 2:
            project_name = question("Enter the project folder name: ").strip()
            if project_name:
                show_generated_project(project_name)
        elif user_input == 3:
            show_uploaded_youtube_shorts(youtube)
        else:
            break



def youtube_guides_menu() -> None:
    while True:
        user_input = ask_menu_choice("Guides", YOUTUBE_GUIDE_OPTIONS)
        if user_input == 1:
            show_content_category_guide()
        elif user_input == 2:
            show_real_video_production_guide()
        else:
            break



def youtube_insights_menu(youtube: YouTube) -> None:
    while True:
        user_input = ask_menu_choice("Topics and Insights", YOUTUBE_INSIGHT_OPTIONS)
        if user_input == 1:
            generate_youtube_insight(youtube, mode="classic")
        elif user_input == 2:
            generate_youtube_insight(youtube, mode="story")
        elif user_input == 3:
            generate_youtube_insight(youtube, mode="finance")
        elif user_input == 4:
            generate_youtube_insight(youtube, mode="biblical")
        else:
            break



def youtube_create_menu(youtube: YouTube, tts: TTS, account: dict) -> None:
    while True:
        user_input = ask_menu_choice("Create Videos", YOUTUBE_CREATE_OPTIONS)
        if user_input == 1:
            generate_youtube_short(youtube, tts, account)
            maybe_upload_youtube_short(youtube)
        elif user_input == 2:
            generated_path = generate_video_reusing_cached_images(youtube, tts)
            if generated_path:
                maybe_upload_youtube_short(youtube)
        elif user_input == 3:
            generate_youtube_narrative_short(youtube, tts, account, mode="story")
            maybe_upload_youtube_short(youtube)
        elif user_input == 4:
            generate_youtube_narrative_short(youtube, tts, account, mode="finance")
            maybe_upload_youtube_short(youtube)
        elif user_input == 5:
            generate_youtube_narrative_short(youtube, tts, account, mode="biblical")
            maybe_upload_youtube_short(youtube)
        elif user_input == 6:
            generate_youtube_long_form_story(youtube, tts, account)
            maybe_upload_youtube_short(youtube)
        elif user_input == 7:
            generate_youtube_feature_video(youtube, tts, account)
            maybe_upload_youtube_short(youtube)
        else:
            break



def get_generated_projects_dir() -> str:
    projects_dir = os.path.join(ROOT_DIR, "outputs", "youtube")
    os.makedirs(projects_dir, exist_ok=True)
    return projects_dir



def list_generated_projects() -> None:
    projects_dir = get_generated_projects_dir()
    project_names = [
        name
        for name in os.listdir(projects_dir)
        if os.path.isdir(os.path.join(projects_dir, name))
    ]
    project_names.sort(reverse=True)

    table = PrettyTable()
    table.field_names = ["Project", "Generated At", "Mode", "Subject", "Video"]

    for project_name in project_names:
        manifest_path = os.path.join(projects_dir, project_name, "manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as file:
                    manifest = json.load(file) or {}
            except Exception:
                manifest = {}

        table.add_row(
            [
                project_name,
                manifest.get("generated_at", ""),
                manifest.get("content_mode", "classic"),
                str(manifest.get("subject", ""))[:60],
                manifest.get("exported_video_path", "video.mp4") or "video.mp4",
            ]
        )

    print(table)



def show_generated_project(project_name: str) -> None:
    project_dir = os.path.join(get_generated_projects_dir(), project_name)
    if not os.path.isdir(project_dir):
        error(f"Project '{project_name}' was not found in outputs/youtube.")
        sys.exit(1)

    manifest_path = os.path.join(project_dir, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file) or {}

    table = PrettyTable()
    table.field_names = ["Field", "Value"]
    table.add_row(["project_dir", project_dir])
    table.add_row(["generated_at", manifest.get("generated_at", "")])
    table.add_row(["subject", manifest.get("subject", "")])
    table.add_row(["content_mode", manifest.get("content_mode", "classic")])
    table.add_row(["profile_name", manifest.get("profile_name", "")])
    table.add_row(["content_brief", manifest.get("content_brief", "")])
    table.add_row(["nickname", manifest.get("nickname", "")])
    table.add_row(["niche", manifest.get("niche", "")])
    table.add_row(["language", manifest.get("language", "")])
    table.add_row(["video", os.path.join(project_dir, "video.mp4")])
    table.add_row(["script", os.path.join(project_dir, "script.txt")])
    table.add_row(["metadata", os.path.join(project_dir, "metadata.json")])
    table.add_row(["prompts", os.path.join(project_dir, "image_prompts.json")])
    table.add_row(["scenes", os.path.join(project_dir, "scenes.json")])
    table.add_row(["visual_bible", os.path.join(project_dir, "visual_bible.json")])
    table.add_row(["references", os.path.join(project_dir, "references.txt")])
    table.add_row(["images", os.path.join(project_dir, "images")])
    table.add_row(["scene_videos", os.path.join(project_dir, "scene_videos")])
    print(table)



def handle_cli_command() -> bool:
    if len(sys.argv) <= 1:
        return False

    command = str(sys.argv[1]).strip().lower()

    if command == "images":
        action = str(sys.argv[2]).strip().lower() if len(sys.argv) > 2 else "list"
        if action == "recover":
            result = recover_image_library()
            success(
                f"Recovered {result['projects_created']} image batch project(s) into {result['library_dir']}"
            )
            return True
        if action == "list":
            table = PrettyTable()
            table.field_names = ["Project", "Type", "Topic", "Images", "Created At"]
            for project in list_image_library_projects():
                table.add_row([
                    project.get("name", ""),
                    project.get("type", ""),
                    str(project.get("topic", ""))[:50],
                    project.get("image_count", 0),
                    project.get("created_at", ""),
                ])
            print(table)
            return True

        error("Unknown images command. Supported: images recover | images list")
        sys.exit(1)

    if command == "projects":
        action = str(sys.argv[2]).strip().lower() if len(sys.argv) > 2 else "list"
        if action == "list":
            list_generated_projects()
            return True
        if action == "show":
            if len(sys.argv) < 4:
                error("Usage: python src/main.py projects show <project_folder_name>")
                sys.exit(1)
            show_generated_project(str(sys.argv[3]).strip())
            return True

        error("Unknown projects command. Supported: projects list | projects show <project_folder_name>")
        sys.exit(1)

    return False



def main():
    """Main entry point for the application, providing a menu-driven interface."""
    valid_input = False
    while not valid_input:
        try:
            info("\n============ OPTIONS ============", False)

            for idx, option in enumerate(OPTIONS):
                print(colored(f" {idx + 1}. {option}", "cyan"))

            info("=================================\n", False)
            user_input = input("Select an option: ").strip()
            if user_input == "":
                print("\n" * 100)
                raise ValueError("Empty input is not allowed.")
            user_input = int(user_input)
            valid_input = True
        except ValueError as e:
            print("\n" * 100)
            print(f"Invalid input: {e}")

    if user_input == 1:
        info("Starting YT Shorts Automater...")

        cached_accounts = get_accounts("youtube")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Firefox profile: ")
                niche = question(" => Enter the account niche: ")
                language = question(" => Enter the account language: ")

                account_data = {
                    "id": generated_uuid,
                    "nickname": nickname,
                    "firefox_profile": fp_profile,
                    "niche": niche,
                    "language": language,
                    "tts_defaults": {},
                    "content_profiles": [
                        {
                            "id": str(uuid4()),
                            "name": "Default",
                            "niche": niche,
                            "language": normalize_video_language(language, "English"),
                            "content_brief": "",
                            "subject_hints": "",
                            "preferred_mode": "classic",
                        }
                    ],
                    "active_content_profile_id": "",
                    "videos": [],
                }

                add_account("youtube", account_data)
                success("Account configured successfully!")
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Niche"]

            for account in cached_accounts:
                table.add_row(
                    [
                        cached_accounts.index(account) + 1,
                        colored(account["id"], "cyan"),
                        colored(account["nickname"], "blue"),
                        colored(account["niche"], "green"),
                    ]
                )

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(
                        f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): "
                    ).strip().lower()

                    if confirm == "yes":
                        remove_account("youtube", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                main()
            else:
                if ensure_youtube_account_profiles(selected_account):
                    update_account(
                        "youtube",
                        selected_account["id"],
                        {
                            "content_profiles": selected_account.get("content_profiles", []),
                            "active_content_profile_id": selected_account.get("active_content_profile_id"),
                            "tts_defaults": selected_account.get("tts_defaults", {}),
                        },
                    )
                if not str(selected_account.get("active_content_profile_id", "")).strip():
                    selected_account["active_content_profile_id"] = selected_account["content_profiles"][0]["id"]
                    update_account("youtube", selected_account["id"], {"active_content_profile_id": selected_account["active_content_profile_id"]})

                youtube = YouTube(
                    selected_account["id"],
                    selected_account["nickname"],
                    selected_account["firefox_profile"],
                    selected_account["niche"],
                    selected_account["language"],
                    tts_defaults=selected_account.get("tts_defaults", {}),
                )
                apply_active_content_profile(selected_account, youtube)

                while True:
                    rem_temp_files()
                    active_profile = apply_active_content_profile(selected_account, youtube)
                    info(
                        f"Active profile: {active_profile.get('name', 'Default')} | Mode: {active_profile.get('preferred_mode', 'classic')} | Niche: {active_profile.get('niche', '')} | Language: {active_profile.get('language', '')}",
                        False,
                    )
                    tts = TTS()
                    user_input = ask_menu_choice("YouTube Workspace", YOUTUBE_OPTIONS)

                    if user_input == 1:
                        youtube_create_menu(youtube, tts, selected_account)
                    elif user_input == 2:
                        youtube_insights_menu(youtube)
                    elif user_input == 3:
                        manage_youtube_content_profiles(selected_account, youtube)
                    elif user_input == 4:
                        upload_current_youtube_video(youtube)
                    elif user_input == 5:
                        review_generated_projects_menu(youtube)
                    elif user_input == 6:
                        show_uploaded_youtube_shorts(youtube)
                    elif user_input == 7:
                        info("How often do you want to upload?")
                        cron_choice = ask_menu_choice("YouTube Automation", YOUTUBE_CRON_OPTIONS)

                        cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                        command = ["python", cron_script_path, "youtube", selected_account["id"], get_active_model()]

                        def job():
                            subprocess.run(command)

                        if cron_choice == 1:
                            schedule.every(1).day.do(job)
                            success("Set up CRON Job.")
                        elif cron_choice == 2:
                            schedule.every().day.at("10:00").do(job)
                            schedule.every().day.at("16:00").do(job)
                            success("Set up CRON Job.")
                        elif cron_choice == 3:
                            schedule.every().day.at("08:00").do(job)
                            schedule.every().day.at("12:00").do(job)
                            schedule.every().day.at("18:00").do(job)
                            success("Set up CRON Job.")
                    elif user_input == 8:
                        youtube_guides_menu()
                    elif user_input == 9:
                        if get_verbose():
                            info(" => Climbing Options Ladder...", False)
                        break
    elif user_input == 2:
        info("Starting Twitter Bot...")

        cached_accounts = get_accounts("twitter")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Firefox profile: ")
                topic = question(" => Enter the account topic: ")

                add_account(
                    "twitter",
                    {
                        "id": generated_uuid,
                        "nickname": nickname,
                        "firefox_profile": fp_profile,
                        "topic": topic,
                        "posts": [],
                    },
                )
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Account Topic"]

            for account in cached_accounts:
                table.add_row(
                    [
                        cached_accounts.index(account) + 1,
                        colored(account["id"], "cyan"),
                        colored(account["nickname"], "blue"),
                        colored(account["topic"], "green"),
                    ]
                )

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(
                        f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): "
                    ).strip().lower()

                    if confirm == "yes":
                        remove_account("twitter", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                main()
            else:
                twitter = Twitter(
                    selected_account["id"],
                    selected_account["nickname"],
                    selected_account["firefox_profile"],
                    selected_account["topic"],
                )

                while True:
                    info("\n============ OPTIONS ============", False)

                    for idx, twitter_option in enumerate(TWITTER_OPTIONS):
                        print(colored(f" {idx + 1}. {twitter_option}", "cyan"))

                    info("=================================\n", False)

                    user_input = int(question("Select an option: "))

                    if user_input == 1:
                        twitter.post()
                    elif user_input == 2:
                        posts = twitter.get_posts()

                        posts_table = PrettyTable()
                        posts_table.field_names = ["ID", "Date", "Content"]

                        for post in posts:
                            posts_table.add_row(
                                [
                                    posts.index(post) + 1,
                                    colored(post["date"], "blue"),
                                    colored(post["content"][:60] + "...", "green"),
                                ]
                            )

                        print(posts_table)
                    elif user_input == 3:
                        info("How often do you want to post?")

                        info("\n============ OPTIONS ============", False)
                        for idx, cron_option in enumerate(TWITTER_CRON_OPTIONS):
                            print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                        info("=================================\n", False)

                        user_input = int(question("Select an Option: "))

                        cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                        command = ["python", cron_script_path, "twitter", selected_account["id"], get_active_model()]

                        def job():
                            subprocess.run(command)

                        if user_input == 1:
                            schedule.every(1).day.do(job)
                            success("Set up CRON Job.")
                        elif user_input == 2:
                            schedule.every().day.at("10:00").do(job)
                            schedule.every().day.at("16:00").do(job)
                            success("Set up CRON Job.")
                        elif user_input == 3:
                            schedule.every().day.at("08:00").do(job)
                            schedule.every().day.at("12:00").do(job)
                            schedule.every().day.at("18:00").do(job)
                            success("Set up CRON Job.")
                        else:
                            break
                    elif user_input == 4:
                        if get_verbose():
                            info(" => Climbing Options Ladder...", False)
                        break
    elif user_input == 3:
        info("Starting Affiliate Marketing...")

        cached_products = get_products()

        if len(cached_products) == 0:
            warning("No products found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                affiliate_link = question(" => Enter the affiliate link: ")
                twitter_uuid = question(" => Enter the Twitter Account UUID: ")

                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == twitter_uuid:
                        account = acc

                add_product(
                    {
                        "id": str(uuid4()),
                        "affiliate_link": affiliate_link,
                        "twitter_uuid": twitter_uuid,
                    }
                )

                afm = AffiliateMarketing(
                    affiliate_link,
                    account["firefox_profile"],
                    account["id"],
                    account["nickname"],
                    account["topic"],
                )

                afm.generate_pitch()
                afm.share_pitch("twitter")
        else:
            table = PrettyTable()
            table.field_names = ["ID", "Affiliate Link", "Twitter Account UUID"]

            for product in cached_products:
                table.add_row(
                    [
                        cached_products.index(product) + 1,
                        colored(product["affiliate_link"], "cyan"),
                        colored(product["twitter_uuid"], "blue"),
                    ]
                )

            print(table)

            user_input = question("Select a product to start: ")

            selected_product = None

            for product in cached_products:
                if str(cached_products.index(product) + 1) == user_input:
                    selected_product = product

            if selected_product is None:
                error("Invalid product selected. Please try again.", "red")
                main()
            else:
                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == selected_product["twitter_uuid"]:
                        account = acc

                afm = AffiliateMarketing(
                    selected_product["affiliate_link"],
                    account["firefox_profile"],
                    account["id"],
                    account["nickname"],
                    account["topic"],
                )

                afm.generate_pitch()
                afm.share_pitch("twitter")

    elif user_input == 4:
        info("Starting Outreach...")

        outreach = Outreach()
        outreach.start()
    elif user_input == 5:
        if get_verbose():
            print(colored(" => Quitting...", "blue"))
        sys.exit(0)
    else:
        error("Invalid option selected. Please try again.", "red")
        main()


if __name__ == "__main__":
    if handle_cli_command():
        sys.exit(0)

    print_banner()

    first_time = get_first_time_running()

    if first_time:
        print(
            colored(
                "Hey! It looks like you're running MoneyPrinter V2 for the first time. Let's get you setup first!",
                "yellow",
            )
        )

    assert_folder_structure()
    rem_temp_files()
    fetch_songs()

    configured_model = get_ollama_model()
    if configured_model:
        select_model(configured_model)
        success(f"Using configured model: {configured_model}")
    else:
        try:
            models = list_models()
        except Exception as e:
            error(f"Could not connect to Ollama: {e}")
            sys.exit(1)

        if not models:
            error("No models found on Ollama. Pull a model first (e.g. 'ollama pull llama3.2:3b').")
            sys.exit(1)

        info("\n========== OLLAMA MODELS =========", False)
        for idx, model_name in enumerate(models):
            print(colored(f" {idx + 1}. {model_name}", "cyan"))
        info("==================================\n", False)

        model_choice = None
        while model_choice is None:
            raw = input(colored("Select a model: ", "magenta")).strip()
            try:
                choice_idx = int(raw) - 1
                if 0 <= choice_idx < len(models):
                    model_choice = models[choice_idx]
                else:
                    warning("Invalid selection. Try again.")
            except ValueError:
                warning("Please enter a number.")

        select_model(model_choice)
        success(f"Using model: {model_choice}")

    while True:
        main()
