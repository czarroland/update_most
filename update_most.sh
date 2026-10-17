#!/bin/sh
# Works on macOS and Linux. Python 3.9+ required.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$HERE/update_most.py" "$@"