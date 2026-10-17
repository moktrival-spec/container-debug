#!/bin/sh
cd "$(dirname "$0")"
python3 -u service.py
status=$?
# A trailing command deliberately prevents a shell tail-exec optimization.
printf 'WRAPPER_EXIT=%s\n' "$status"
exit "$status"
