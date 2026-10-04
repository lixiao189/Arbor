"""Launch a built Arbor bundle and check that it starts and stays up.

Usage: python packaging/smoke_test.py <path to the Arbor executable>

The bundle drops Qt's offscreen platform plugin, so this needs a real display
(xvfb-run on Linux; the macOS and Windows runners have a desktop session).
"""

import subprocess
import sys

STARTUP_SECONDS = 10


def main() -> None:
    proc = subprocess.Popen([sys.argv[1]])
    try:
        code = proc.wait(timeout=STARTUP_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print(f"Arbor still running after {STARTUP_SECONDS}s: OK")
        return
    sys.exit(f"Arbor exited early with code {code}")


if __name__ == "__main__":
    main()
