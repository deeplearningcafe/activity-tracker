"""System idle time tracking via xprintidle.

Invokes the ``xprintidle`` utility (installed via ``apt install xprintidle``)
to query the X server for the user's inactivity duration in milliseconds.
"""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def get_idle_ms() -> int:
    """Query the X server for the user's idle time in milliseconds.

    Invokes ``xprintidle`` via subprocess. If the utility is unavailable,
    the X server is inaccessible, or the command fails for any reason,
    returns 0 as a safe default.

    Returns:
        The idle time in milliseconds, or 0 on failure.
    """
    try:
        result = subprocess.run(
            ["xprintidle"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug("xprintidle exited with code %d", result.returncode)
            return 0
        idle_ms = int(result.stdout.strip())
        return idle_ms
    except FileNotFoundError:
        logger.debug("xprintidle not found in PATH")
        return 0
    except subprocess.TimeoutExpired:
        logger.debug("xprintidle timed out after 5 seconds")
        return 0
    except (ValueError, OSError) as exc:
        logger.debug("xprintidle error: %s", exc)
        return 0
