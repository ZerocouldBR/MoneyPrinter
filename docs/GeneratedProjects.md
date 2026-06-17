# Generated YouTube Project Folders

MoneyPrinter now exports each generated YouTube short into its own project folder under:

```text
outputs/youtube/
```

A typical project folder looks like this:

```text
outputs/youtube/20260617-103500-ai-and-automation/
  video.mp4
  manifest.json
  metadata.json
  script.txt
  image_prompts.json
  references.txt
  images/
```

## What each file contains

- `video.mp4`: final rendered video
- `script.txt`: the exact narration script used for TTS
- `image_prompts.json`: prompts used to generate the images
- `metadata.json`: title, description, and related metadata
- `references.txt`: source, source URL, briefing, and research context
- `manifest.json`: full structured record for the generated project
- `images/`: copies of the images used in the final video

## Interactive workflow

From the main menu:
1. Select `YouTube Shorts Automation`
2. Select an account
3. Choose `Upload Short`
4. Press `ENTER` for automatic topic/script generation, or enter a custom topic
5. Optionally provide your own full script and finish with `END`
6. After rendering, review the generated project folder in `outputs/youtube/`

## CLI review commands

```bash
python src/main.py projects list
python src/main.py projects show <project_folder_name>
```

`projects list` shows all generated project folders.

`projects show` prints the main files and metadata paths for a single generated project.
