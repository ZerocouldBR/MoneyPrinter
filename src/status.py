import sys
from termcolor import colored


def _safe_text(message: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        message.encode(encoding)
        return message
    except UnicodeEncodeError:
        return message.encode(encoding, errors="replace").decode(encoding)


def _emit(message: str, color: str) -> None:
    print(colored(_safe_text(message), color))


def error(message: str, show_emoji: bool = True) -> None:
    """
    Prints an error message.

    Args:
        message (str): The error message
        show_emoji (bool): Whether to show the emoji

    Returns:
        None
    """
    emoji = "❌" if show_emoji else ""
    _emit(f"{emoji} {message}", "red")


def success(message: str, show_emoji: bool = True) -> None:
    """
    Prints a success message.

    Args:
        message (str): The success message
        show_emoji (bool): Whether to show the emoji

    Returns:
        None
    """
    emoji = "✅" if show_emoji else ""
    _emit(f"{emoji} {message}", "green")


def info(message: str, show_emoji: bool = True) -> None:
    """
    Prints an info message.

    Args:
        message (str): The info message
        show_emoji (bool): Whether to show the emoji

    Returns:
        None
    """
    emoji = "ℹ️" if show_emoji else ""
    _emit(f"{emoji} {message}", "magenta")


def warning(message: str, show_emoji: bool = True) -> None:
    """
    Prints a warning message.

    Args:
        message (str): The warning message
        show_emoji (bool): Whether to show the emoji

    Returns:
        None
    """
    emoji = "⚠️" if show_emoji else ""
    _emit(f"{emoji} {message}", "yellow")


def question(message: str, show_emoji: bool = True) -> str:
    """
    Prints a question message and returns the user's input.

    Args:
        message (str): The question message
        show_emoji (bool): Whether to show the emoji

    Returns:
        user_input (str): The user's input
    """
    emoji = "❓" if show_emoji else ""
    return input(colored(_safe_text(f"{emoji} {message}"), "magenta"))
