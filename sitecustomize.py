"""Runtime compatibility shims for third-party dependencies.

Python imports this module automatically at startup when it is available on
sys.path. Keep this file small and limited to safe compatibility aliases.
"""

try:
    from PIL import Image

    if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
except Exception:
    # Do not block application startup if Pillow is not installed yet or if
    # the runtime changes. The application will surface the original error
    # later if image processing is unavailable.
    pass
