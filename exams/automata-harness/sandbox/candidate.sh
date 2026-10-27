#!/bin/sh
# One sitting only. Python finally/signal cleanup + independent lifetime guard.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/candidate.py" "$@"
