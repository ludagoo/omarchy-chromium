#!/bin/bash
# Runs the checks behind the results in the CL files, as root, on a machine
# with a V4L2 stateless decoder and a Wayland session.
#   run-tests.sh unit|play|picture|analyse|reschange|vdat|all
#
# Environment:
#   OUT          Chromium out dir (use_v4l2_codec=true) with chrome,
#                media_unittests and, for vdat, video_decode_accelerator_tests
#   SRC          Chromium src dir (vdat uses media/test/data); default OUT/../..
#   CLIPS        directory with the test clips (names below)
#   WORK         scratch and results directory; default ./work
#   CHROME_USER  user whose Wayland session runs Chrome
#   PY           python with the "websockets" module; default python3
#
# The fade clips come from make-fade-clips.sh. The other clips are short
# (4 or 20 second) encodes of a 1080p or 2160p source: H.264 High, HEVC Main
# (hevc10-1080p30 is 8-bit despite its name) and Main 10, VP9 profiles 0 and 2.
# The slice clips were made with x264 --slices 4 and --slice-max-size 1200.
set -u
: "${OUT:?set OUT}" "${CLIPS:?set CLIPS}" "${CHROME_USER:?set CHROME_USER}"
SRC=${SRC:-$OUT/../..}
WORK=${WORK:-$PWD/work}
PY=${PY:-python3}
T=$(cd "$(dirname "$0")" && pwd)
R=$WORK/results
export CHROME_USER
# A build without VA-API leaves the hardware decoder off by default.
export SR_FEATURES=${SR_FEATURES:-AcceleratedVideoDecoder}
export SR_EXTRA=${SR_EXTRA:---enable-features=AcceleratedVideoDecoder}
PLAYLIST="h264-1080p30.mp4 h264-2160p30.mp4 hevc-1080p30.mp4 hevc-2160p30.mp4
  hevc10-1080p30.mp4 vp9-1080p30.webm vp9-2160p30.webm vp9p2-1080p30.webm
  h264-1080p30-slices4.mp4 h264-1080p30-slicemax.mp4 hevc-main10-1080p30.mp4
  vp9-profile2-1080p30.webm"
FADE="hevc-fade-1080p30.mp4 h264-fade-1080p30.mp4"
mkdir -p "$R"

clips() { for c in "$@"; do [ -e "$CLIPS/$c" ] && echo "$CLIPS/$c"; done; }

unit() {
  "$OUT/media_unittests" --gtest_filter='*V4L2*' --single-process-tests \
    > "$R/media_unittests-v4l2.txt" 2>&1
  echo "media_unittests exit $?" >> "$R/media_unittests-v4l2.txt"
  tail -5 "$R/media_unittests-v4l2.txt"
}

play() {
  # shellcheck disable=SC2046,SC2086
  "$PY" "$T/sr-play.py" r2 "$OUT/chrome" 9341 $(clips $PLAYLIST $FADE) \
    > "$R/play.txt" 2>&1
  grep -v "^decoder" "$R/play.txt"
}

picture() {
  mkdir -p "$WORK/frames"
  export PICTURE_CANVAS=1 PICTURE_SEEK_MS=30000
  # shellcheck disable=SC2046,SC2086
  { "$PY" "$T/sr-picture.py" r2 "$OUT/chrome" 9342 "$WORK/frames" $(clips $PLAYLIST)
    PICK=0.03,0.15,0.45,0.6,0.75 "$PY" "$T/sr-picture.py" r2f "$OUT/chrome" 9343 \
      "$WORK/frames" $(clips $FADE); } > "$R/picture.txt" 2>&1
  cat "$R/picture.txt"
}

# Per-pixel check of the frames picture() saved: is each Chrome frame a fixed
# function of an FFmpeg frame? FFmpeg's frame numbers can be a few frames off
# Chrome's timestamps, so FFmpeg frames k, k-1, k+1, ... k+3 are tried until
# one maps with zero error. Every attempt is printed.
analyse() {
  local f base k clip n pix ref line wh
  for f in "$WORK"/frames/*.chrome.nv12 "$WORK"/frames/*.chrome.rgba; do
    [ -e "$f" ] || continue
    base=$(basename "$f"); clip=${base%%.f[0-9]*}; k=${base#"$clip".f}; k=${k%%.*}
    pix=nv12; [ "${f##*.}" = rgba ] && pix=p010le
    wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
      -of csv=p=0:s=x "$CLIPS/$clip"); wh=${wh/x/ }
    echo "== $clip chrome frame $k"
    for n in $k $((k - 1)) $((k + 1)) $((k - 2)) $((k + 2)) $((k - 3)) $((k + 3)); do
      [ "$n" -ge 0 ] || continue
      ref=$WORK/frames/$clip.ref$n.$pix
      [ -e "$ref" ] || ffmpeg -v error -y -i "$CLIPS/$clip" -vf "select=eq(n\,$n)" \
        -frames:v 1 -f rawvideo -pix_fmt "$pix" "$ref"
      if [ $pix = nv12 ]; then
        # shellcheck disable=SC2086
        line=$("$PY" "$T/pixmap.py" "$f" "$ref" $wh | head -1)
      else
        # shellcheck disable=SC2086
        line=$("$PY" "$T/pixmap10.py" "$f" "$ref" $wh)
      fi
      echo "ffmpeg frame $n: $line"
      case $line in *"mapping=0.000"*|*"RGB=0.000%"*) break ;; esac
    done
  done > "$R/analyse.txt" 2>&1
  cat "$R/analyse.txt"
}

# The resolution-change streams, muxed to MP4 and played through.
reschange() {
  local c
  mkdir -p "$WORK/reschange"
  [ -e "$WORK/reschange/hevc-reschange.hevc" ] || "$T/make-reschange-clips.sh" "$WORK/reschange"
  for c in h264 hevc; do
    ffmpeg -v error -y -r 30 -i "$WORK/reschange/$c-reschange.$c" -c copy \
      $([ $c = hevc ] && echo -tag:v hvc1) "$WORK/reschange/$c-reschange.mp4"
  done
  PLAY_WAIT=8 "$PY" "$T/sr-play.py" r2res "$OUT/chrome" 9344 \
    "$WORK"/reschange/{h264,hevc}-reschange.mp4 > "$R/reschange.txt" 2>&1
  cat "$R/reschange.txt"
}

# video_decode_accelerator_tests does not run on desktop Linux at this base:
# HEVC and VP9 crash in the test's frame wrapper, and the H.264 reader feeds
# one NAL unit per buffer, which fails any multi-slice stream. Kept for
# platforms where it runs.
vdat() {
  local V=$WORK/vdat c v
  mkdir -p "$V" "$WORK/reschange"
  [ -e "$WORK/reschange/hevc-reschange.hevc" ] || "$T/make-reschange-clips.sh" "$WORK/reschange"
  for c in $(clips h264-1080p30.mp4 hevc-1080p30.mp4 vp9-1080p30.webm \
      h264-1080p30-slices4.mp4 h264-1080p30-slicemax.mp4 hevc-main10-1080p30.mp4 \
      vp9-profile2-1080p30.webm $FADE) "$WORK"/reschange/*-reschange.*; do
    "$PY" "$T/make-vdat-json.py" "$c" "$V"
  done
  for v in "$SRC"/media/test/data/test-25fps.{h264,hevc,vp9} "$V"/*.h264 "$V"/*.hevc "$V"/*.ivf; do
    [ -e "$v" ] || continue
    echo "== $(basename "$v")"
    "$OUT/video_decode_accelerator_tests" "$v" "$v.json" \
      --gtest_filter='VideoDecoderTest.FlushAtEndOfStream' 2>&1 | tail -15
  done > "$R/video_decode_accelerator_tests.txt"
  cat "$R/video_decode_accelerator_tests.txt"
}

case "${1:-all}" in
  unit) unit ;; play) play ;; picture) picture ;; analyse) analyse ;;
  reschange) reschange ;; vdat) vdat ;;
  all) unit; play; picture; analyse; reschange ;;
  *) echo "usage: $0 unit|play|picture|analyse|reschange|vdat|all"; exit 2 ;;
esac
