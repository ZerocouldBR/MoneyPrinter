# Image Library Recovery and Reuse

MoneyPrinter now supports organizing older saved images into a reusable image library.

## Library location

```text
outputs/image_library/
```

Each recovered image batch is stored in its own folder with:
- `manifest.json`
- `references.txt`
- `images/`

## Important note

Older cached images may not have prompt metadata available.

When that happens, MoneyPrinter recovers and preserves the images, but marks them as:
- `prompt_status: unknown_recovered`
- `topic_status: inferred_from_youtube_account_niche`

This means the images were successfully preserved, but their original prompts could not be reconstructed from the older cache.

## Commands

```bash
python src/main.py images recover
python src/main.py images list
```

- `images recover`: scans `.mp/` and `.mp/image_cache/`, groups images by generation session, deduplicates them, and copies them into `outputs/image_library/`
- `images list`: lists recovered image-library projects

## Future generations

For future YouTube videos, MoneyPrinter stores a full project folder in `outputs/youtube/` with:
- script
- prompts
- references
- metadata
- images
- final video

That is the preferred long-term archive format.
