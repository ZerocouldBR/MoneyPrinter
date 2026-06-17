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
from llm_provider import list_models, select_model, get_active_model
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


def prompt_youtube_generation_inputs() -> tuple[str | None, str | None]:
    info("Press ENTER to use automatic topic/script generation.", False)
    custom_topic = question("Optional custom topic: ").strip()
    if not custom_topic:
        return None, None

    if not ask_yes_no("Do you want to provide your own full script? (Yes/No): "):
        return custom_topic, None

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
    return custom_topic, custom_script or None


def generate_youtube_short(youtube: YouTube, tts: TTS) -> None:
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


def generate_youtube_narrative_short(youtube: YouTube, tts: TTS, mode: str) -> None:
    custom_topic, custom_script = prompt_youtube_generation_inputs()
    planner = NarrativeModeService()
    plan = planner.build_plan(
        mode=mode,
        niche=youtube.niche,
        language=youtube.language,
        topic_override=custom_topic,
        script_override=custom_script,
    )
    info(f"Narrative mode selected: {plan['mode_label']}", False)
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
                youtube = YouTube(
                    selected_account["id"],
                    selected_account["nickname"],
                    selected_account["firefox_profile"],
                    selected_account["niche"],
                    selected_account["language"],
                )

                while True:
                    rem_temp_files()
                    info("\n============ OPTIONS ============", False)

                    for idx, youtube_option in enumerate(YOUTUBE_OPTIONS):
                        print(colored(f" {idx + 1}. {youtube_option}", "cyan"))

                    info("=================================\n", False)

                    user_input = int(question("Select an option: "))
                    tts = TTS()

                    if user_input == 1:
                        generate_youtube_short(youtube, tts)
                        maybe_upload_youtube_short(youtube)
                    elif user_input == 2:
                        generated_path = generate_video_reusing_cached_images(youtube, tts)
                        if generated_path:
                            maybe_upload_youtube_short(youtube)
                    elif user_input == 3:
                        generate_youtube_narrative_short(youtube, tts, mode="story")
                        maybe_upload_youtube_short(youtube)
                    elif user_input == 4:
                        generate_youtube_narrative_short(youtube, tts, mode="finance")
                        maybe_upload_youtube_short(youtube)
                    elif user_input == 5:
                        generate_youtube_narrative_short(youtube, tts, mode="biblical")
                        maybe_upload_youtube_short(youtube)
                    elif user_input == 6:
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
                            warning(" No videos found.")
                    elif user_input == 7:
                        info("How often do you want to upload?")

                        info("\n============ OPTIONS ============", False)
                        for idx, cron_option in enumerate(YOUTUBE_CRON_OPTIONS):
                            print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                        info("=================================\n", False)

                        user_input = int(question("Select an Option: "))

                        cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                        command = ["python", cron_script_path, "youtube", selected_account["id"], get_active_model()]

                        def job():
                            subprocess.run(command)

                        if user_input == 1:
                            schedule.every(1).day.do(job)
                            success("Set up CRON Job.")
                        elif user_input == 2:
                            schedule.every().day.at("10:00").do(job)
                            schedule.every().day.at("16:00").do(job)
                            success("Set up CRON Job.")
                        else:
                            break
                    elif user_input == 8:
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
