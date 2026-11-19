#!/bin/bash
# Runs sr-play.py over the 12 clips for one browser with the Studio builds
# paused (SIGSTOP) and always resumed afterward. Run as root on the Studio.
#   sr-bench.sh NAME CHROME PORT   (env passed through to sr-play.py)
set -u
H=$(dirname "$(readlink -f "$0")")
C=/home/smartroomcontroller/.local/share/smartroom-qa/clips
CLIPS="h264-1080p30.mp4 h264-2160p30.mp4 hevc-1080p30.mp4 hevc-2160p30.mp4 hevc10-1080p30.mp4 vp9-1080p30.webm vp9-2160p30.webm vp9p2-1080p30.webm h264-1080p30-slices4.mp4 h264-1080p30-slicemax.mp4 hevc-main10-1080p30.mp4 vp9-profile2-1080p30.webm"
UNITS="srbuild-chromium-v4l2-a srbuild-room-158-build"
resume() { for u in $UNITS; do systemctl kill -s SIGCONT $u 2>/dev/null; done; echo "builds resumed $(date -Is)"; }
trap resume EXIT
for u in $UNITS; do systemctl kill -s SIGSTOP $u 2>/dev/null; done
sleep 5; echo "builds paused $(date -Is) load $(cut -d' ' -f1-3 /proc/loadavg)"
J0=$(journalctl -k -q --no-pager -n0 --show-cursor | sed -n 's/^-- cursor: //p')
args=(); for c in $CLIPS; do args+=("$C/$c"); done
PLAY_WAIT=${PLAY_WAIT:-24} "$H/sr-play.py" "$1" "$2" "$3" "${args[@]}"
echo "kernel avd lines during run:"; journalctl -k -q --no-pager --after-cursor="$J0" | grep -i -E 'avd|ave' | tail -15
