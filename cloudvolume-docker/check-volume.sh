#!/bin/sh
# Refuse to start when the mount is not a precomputed volume. Replaces the old
# launcher's CloudVolume(...)[1,1,1] sanity read.
set -e
if [ ! -s /mnt/data/info ]; then
    echo "check-volume: /mnt/data/info missing or empty; not a precomputed volume" >&2
    exit 1
fi
grep -q '"scales"' /mnt/data/info || { echo "check-volume: info has no scales" >&2; exit 1; }
