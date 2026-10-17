#!/bin/sh
# Double-clickable Terminal launcher for macOS. Requires Python 3.9+.
cd "$(dirname "$0")" || exit 1
./update_most.sh "$@"
echo ""
printf 'Press Enter to close... '
read -r unused