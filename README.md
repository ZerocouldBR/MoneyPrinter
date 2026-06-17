# MoneyPrinter V2

Sponsored by Post Bridge

<a href="https://post-bridge.com?atp=MoneyPrinter">
  <img src="docs/repo/PostBridgeBanner.png" alt="Post Bridge integration banner" width="720" />
</a>


[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/FujiwaraChoki/MoneyPrinterV2)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-brightgreen?logo=buymeacoffee)](https://www.buymeacoffee.com/fujicodes)
[![GitHub license](https://img.shields.io/github/license/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/issues)
[![GitHub stars](https://img.shields.io/github/stars/FujiwaraChoki/MoneyPrinterV2?style=for-the-badge)](https://github.com/FujiwaraChoki/MoneyPrinterV2/stargazers)
[![Discord](https://img.shields.io/discord/1134848537704804432?style=for-the-badge)](https://dsc.gg/fuji-community)

An Application that automates the process of making money online.
MPV2 (MoneyPrinter Version 2) is, as the name suggests, the second version of the MoneyPrinter project. It is a complete rewrite of the original project, with a focus on a wider range of features and a more modular architecture.

> **Note:** MPV2 needs Python 3.12 to function effectively.
> Watch the YouTube video [here](https://youtu.be/wAZ_ZSuIqfk)

## Features

- [x] Twitter Bot (with CRON Jobs => `scheduler`)
- [x] YouTube Shorts Automator (with CRON Jobs => `scheduler`)
- [x] Affiliate Marketing (Amazon + Twitter)
- [x] Find local businesses & cold outreach

## Versions

MoneyPrinter has different versions for multiple languages developed by the community for the community. Here are some known versions:

- Chinese: [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)

If you would like to submit your own version/fork of MoneyPrinter, please open an issue describing the changes you made to the fork.

## Installation

> ⚠️ If you are planning to reach out to scraped businesses per E-Mail, please first install the [Go Programming Language](https://golang.org/).

### Windows / PowerShell

Use Python 3.12. Python 3.13 is not supported by all current dependencies.

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
Copy-Item config.example.json config.json
python src/main.py
```

If PowerShell blocks virtual environment activation, run this once and activate the environment again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
git clone https://github.com/FujiwaraChoki/MoneyPrinterV2.git
cd MoneyPrinterV2

# Copy Example Configuration and fill out values in config.json
cp config.example.json config.json

# Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install the requirements
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Dependency compatibility notes

The project currently pins a few dependencies to keep compatibility with the existing imports:

- `selenium==4.9.1` keeps compatibility with `selenium_firefox==2.0.8`.
- `moviepy==1.0.3` keeps compatibility with `from moviepy.editor import *`.

If you already installed dependencies before these pins were added, refresh your local environment with:

```powershell
pip install --force-reinstall -r requirements.txt
```

## Usage

### Interactive app

```bash
python src/main.py
```

### Generated video projects

Each generated YouTube short is now exported into its own project folder under:

```text
outputs/youtube/
```

Each project folder contains:
- `video.mp4`
- `script.txt`
- `image_prompts.json`
- `scenes.json`
- `visual_bible.json`
- `metadata.json`
- `references.txt`
- `manifest.json`
- `images/`
- `scene_videos/` (when scene video generation is enabled)

### Project review commands

```bash
# List generated YouTube video projects
python src/main.py projects list

# Show details for one generated project folder
python src/main.py projects show <project_folder_name>

# Recover older cached images into an organized image library
python src/main.py images recover

# List recovered image-library batches
python src/main.py images list
```

### Narrative creation modes

The YouTube flow now supports dedicated narrative modes:
- `Create Story Short`
- `Create Market Commentary Short`
- `Create Biblical / Devotional Short`

These modes generate:
- a subject
- a coherent short script
- a visual bible
- scene-by-scene prompts with continuity

### Image generation provider config

You can now configure the image-generation layer in `config.json`:

```json
"image_generation": {
  "provider": "gemini",
  "consistency_level": "high",
  "use_reference_images": false,
  "gemini_api_base_url": "https://generativelanguage.googleapis.com/v1beta",
  "gemini_api_key": "",
  "gemini_model": "gemini-3.1-flash-image-preview",
  "aspect_ratio": "9:16"
}
```

The current build supports Gemini directly through the provider abstraction and is prepared for future provider integrations.

### Optional scene video generation

You can optionally enable scene video generation for narrative modes using either MiniMax or Gemini/Veo-compatible configuration:

```json
"video_generation": {
  "enabled": false,
  "provider": "none",
  "mode": "hybrid",
  "generate_first_n_scenes": 1,
  "duration_seconds": 6,
  "resolution": "1080P"
}
```

When enabled, narrative modes can generate the first N scenes as video clips and fall back to images for the rest.

### Manual topic or script input

In the YouTube flow, choose `Upload Short` and then:
- press `ENTER` to keep automatic topic and script generation, or
- provide a custom topic, and optionally
- paste your own full script and finish with a line containing only `END`

## Documentation

All relevant documents can be found [here](docs/).

Additional project workflow documentation:
- [Generated YouTube Project Folders](docs/GeneratedProjects.md)
- [Image Library Recovery and Reuse](docs/ImageLibrary.md)
- [Narrative Modes](docs/NarrativeModes.md)

## Scripts

For easier usage, there are some scripts in the `scripts` directory that can be used to directly access the core functionality of MPV2 without the need for user interaction.

All scripts need to be run from the root directory of the project, e.g. `bash scripts/upload_video.sh`.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us. Check out [docs/Roadmap.md](docs/Roadmap.md) for a list of features that need to be implemented.

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

MoneyPrinterV2 is licensed under `Affero General Public License v3.0`. See [LICENSE](LICENSE) for more information.

## Acknowledgments

- [KittenTTS](https://github.com/KittenML/KittenTTS)
- [gpt4free](https://github.com/xtekky/gpt4free)

## Disclaimer

This project is for educational purposes only. The author will not be responsible for any misuse of the information provided. All the information on this website is published in good faith and for general information purposes only. The author does not make any warranties about the completeness, reliability, and accuracy of this information. Any action you take upon the information you find on this website (FujiwaraChoki/MoneyPrinterV2) is strictly at your own risk. The author will not be liable for any losses and/or damages in connection with the use of our website.
