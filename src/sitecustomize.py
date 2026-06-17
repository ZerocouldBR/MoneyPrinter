"""Runtime compatibility shims for third-party dependencies.

Python imports this module automatically at startup when it is available on
sys.path. Keep this file small and limited to safe compatibility aliases.
"""

import sys


def _enable_utf8_console_on_windows() -> None:
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_enable_utf8_console_on_windows()

try:
    from PIL import Image

    if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
except Exception:
    # Do not block application startup if Pillow is not installed yet or if
    # the runtime changes. The application will surface the original error
    # later if image processing is unavailable.
    pass
