#!/bin/bash
# WebRTC loopback on the Studio for private Chromium builds. Run as root.
#   sr-webrtc.sh NAME RECV_CHROME [SEND_CHROME]
# The sender (default: RECV_CHROME) sends a 1280x720 15 fps fake camera as H.264
# constrained baseline (OpenH264 unless the build has a Linux encoder), with
# its decoder nodes hidden so it never holds the decoder. Both sides keep every
# sandbox on and run as smartroomcontroller with throwaway profiles under
# ~/.cache/sr-upstream; ports 8770/8771 (relay), 9349 (receiver), 9350 (sender).
# Never port 9222, never the kiosk profile.
# Environment:
#   PROFILE=cb|high   high: the relay tells the receiver the stream is H.264 High
#                     (FORCE_ID, default 64001f = High 3.1; 640c1f is Constrained High)
#   HIDE=none|start|after  receiver decoder nodes: present; absent from launch;
#                     present at GPU start, then gone before the call (the V4L2
#                     decoder is offered but its initialization fails)
#   RECV_FEATURES=... --enable-features for the receiver
#   SEND_FEATURES=... --enable-features for the sender (e.g. AcceleratedVideoEncoder)
#   RECV_EXTRA="..."  more receiver switches
#   T=20              seconds of call before the receiver reports
set -u
NAME=$1; RECV=$2; SEND=${3:-$2}
PROFILE=${PROFILE:-cb}; HIDE=${HIDE:-none}; T=${T:-20}
H=$(dirname "$(readlink -f "$0")")
U=smartroomcontroller; UH=/home/$U; RUN=/run/user/$(id -u $U)
D=$UH/.cache/sr-upstream/webrtc-$NAME; LOG=/tmp/sr-webrtc-$NAME
CAM=$UH/.cache/sr-decode-ms/cam720.y4m
NODES="/dev/video0 /dev/media0 /dev/video-dec0 /dev/media-dec0"
WL=$(ls $RUN | grep -m1 -E '^wayland-[0-9]+$'); SIG=$(ls -t $RUN/hypr | head -1)
UENV="XDG_RUNTIME_DIR=$RUN WAYLAND_DISPLAY=$WL HYPRLAND_INSTANCE_SIGNATURE=$SIG DBUS_SESSION_BUS_ADDRESS=unix:path=$RUN/bus HOME=$UH"
RELAY=""; SPID=""; RPID=""
binds() { for n in $NODES; do [ -e $n ] && echo "mount --bind /dev/null $n;"; done; }
desc() {  # PID and all its descendants
  ps -e -o pid=,ppid= | awk -v r="$1" '{k[$2]=k[$2]" "$1} END{q[1]=r; n=1; for(i=1;i<=n;i++){print q[i]; m=split(k[q[i]],c," "); for(j=1;j<=m;j++) q[++n]=c[j]}}'
}
cleanup() {
  for p in $(pgrep -u $U -f "user-data-dir=$D/"); do
    tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | grep -q -- '--type=' || kill $p 2>/dev/null
  done
  sleep 3
  for r in $RPID $SPID; do for p in $(desc $r); do kill -9 $p 2>/dev/null; done; done
  [ -n "$RELAY" ] && kill $RELAY 2>/dev/null
  true
}
trap cleanup EXIT
echo "START $(date -Is) name=$NAME profile=$PROFILE hide=$HIDE"
[ -e /home/lucas/smartroom-aurora-kernel/HOLD-REBOOTS ] && { echo HOLD; exit 2; }
ss -ltn | grep -qE ':(8770|8771|9349|9350) ' && { echo PORT_TAKEN; ss -ltnp | grep -E ':(8770|8771|9349|9350) '; exit 8; }
[ -f "$CAM" ] || { echo NO_CAM; exit 5; }
rm -rf "$D"; mkdir -p "$D/send" "$D/recv" "$LOG"; chown -R $U:$U "$UH/.cache/sr-upstream"
rm -f "$H/webrtc/stats.json" "$H/webrtc/sender-stats.json"
[ "$PROFILE" = high ] && export SR_FORCE_PROFILE=${FORCE_ID:-64001f} || unset SR_FORCE_PROFILE
/opt/smartroom/venv/bin/python "$H/webrtc/relay.py" >"$LOG/relay.log" 2>&1 &
RELAY=$!; sleep 0.5; kill -0 $RELAY || { echo RELAY_DEAD; cat "$LOG/relay.log"; exit 6; }

COMMON="--enable-gpu --use-gl=angle --use-angle=gles-egl --render-node-override=/dev/dri/renderD128 --enable-logging=stderr --no-first-run --no-default-browser-check --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required --use-fake-ui-for-media-stream --ozone-platform=wayland --ozone-platform-hint=wayland"
cd "$(dirname "$SEND")"
unshare --mount --propagation private bash -c "$(binds) exec runuser -u $U -- env $UENV '$SEND' $COMMON \
  ${SEND_FEATURES:+--enable-features=$SEND_FEATURES} \
  --use-fake-device-for-media-stream --use-file-for-fake-video-capture=$CAM \
  --remote-debugging-port=9350 --user-data-dir=$D/send --class=sr-upstream-send --window-size=480,360 \
  'http://127.0.0.1:8770/?one=1'" >"$LOG/send.err" 2>&1 &
SPID=$!
for i in $(seq 30); do grep -q "joined sender" "$LOG/relay.log" && break; sleep 1; done
grep -q "joined sender" "$LOG/relay.log" || { echo SENDER_NO_JOIN; tail -20 "$LOG/send.err"; exit 1; }
runuser -u $U -- env $UENV hyprctl dispatch movetoworkspacesilent 1,class:sr-upstream-send >/dev/null

PRE=""; [ "$HIDE" = start ] && PRE=$(binds)
cd "$(dirname "$RECV")"
unshare --mount --propagation private bash -c "$PRE exec runuser -u $U -- env $UENV '$RECV' $COMMON \
  ${RECV_FEATURES:+--enable-features=$RECV_FEATURES} ${RECV_EXTRA:-} \
  --vmodule=v4l2_codec_nodes=1,v4l2_video_decoder=1,v4l2_device=1,v4l2_video_decoder_backend_stateless=1,rtc_video_decoder_adapter=2,video_codec_factory=2 \
  --use-fake-device-for-media-stream --remote-debugging-port=9349 --user-data-dir=$D/recv \
  --class=sr-upstream-recv --window-size=640,360 about:blank" >"$LOG/recv.err" 2>&1 &
RPID=$!
for i in $(seq 40); do curl -s 127.0.0.1:9349/json/version >/dev/null && break; sleep 0.5; done
runuser -u $U -- env $UENV hyprctl dispatch movetoworkspacesilent 1,class:sr-upstream-recv >/dev/null
sleep 6
if [ "$HIDE" = after ]; then
  nsenter --target $RPID --mount bash -c "$(binds)" && echo "decoder nodes hidden after GPU start"
fi
curl -s -X PUT "127.0.0.1:9349/json/new?http://127.0.0.1:8770/receiver?t=$T" >/dev/null
tj() { for p in $(desc $RPID); do awk '{print $14+$15}' /proc/$p/stat 2>/dev/null; done | awk '{s+=$1} END{print s+0}'; }
J0=$(tj); T0=$(date +%s.%N)
GPU=$(for p in $(desc $RPID); do tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | grep -q -- '--type=gpu-process' && echo $p; done | head -1)
for i in $(seq $((T + 30))); do
  grep -q "^STATS " "$LOG/relay.log" && break
  [ $i = $((T / 2)) ] && HELD=$(ls -l /proc/$GPU/fd 2>/dev/null | grep -oE '/dev/(video|media)[^ ]*' | sort -u | tr '\n' ' ')
  sleep 1
done
J1=$(tj); T1=$(date +%s.%N)
echo "recv_cpu_pct=$(awk -v a=$J0 -v b=$J1 -v s=$T0 -v e=$T1 -v hz=$(getconf CLK_TCK) 'BEGIN{printf "%.1f", (b-a)*100/hz/(e-s)}') (receiver tree, % of one core; gpu pid ${GPU:-?})"
echo "recv_gpu_nodes=${HELD:-none}"
echo "=== relay ==="; grep -E "^(STATS|SENDER|munged)" "$LOG/relay.log"
echo "=== receiver log ==="
grep -E "V4L2 (codec|media) node|No V4L2|V4L2VideoDecoder|Fallback|fallback|NullVideo|InitDecode|decoder init|Failed to (open|create)" "$LOG/recv.err" \
  | grep -v -E "crashpad|dbus|GCM" | sed 's/^\[[^]]*\]//' | sort | uniq -c | head -30
echo "=== internals ==="
/opt/smartroom/venv/bin/python "$H/webrtc/ms-internals.py" 9349 9350 2>&1 | grep -A40 -E "^(WEBRTC_INTERNALS|SENDER_LOG)" | grep -E "decoder|Decoder|encoder|Encoder|sending|h264|sdp|ENCODER|framesDecoded|SEND_FAIL" | head -30
grep -q "^STATS " "$LOG/relay.log" && echo WEBRTC_DONE || { echo WEBRTC_NO_STATS; tail -20 "$LOG/recv.err"; }
