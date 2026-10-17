#!/bin/sh
# Works on macOS and Linux. Python 3.9+ required.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then
  set -- --menu
fi
exec python3 "$HERE/update_most.py" "$@"
