#!/bin/bash
# Makes elementary streams that change resolution mid-stream, in DIR
# (default .), for video_decode_accelerator_tests:
#   h264-reschange.h264, hevc-reschange.hevc
# Each is 45 frames at 640x360, 45 at 1280x720 and 45 at 640x360, every part
# starting with an IDR picture and its own parameter sets. The step from 360p
# to 720p crosses a coded-buffer size, so the decoder must reallocate.
set -eu
DIR=${1:-.}
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
i=0
for s in 640x360 1280x720 640x360; do
  i=$((i + 1))
  src=(-f lavfi -i "testsrc2=size=$s:rate=30:duration=1.5" -pix_fmt yuv420p)
  ffmpeg -v error -y "${src[@]}" -c:v libx264 -profile:v high -bf 2 -g 45 \
    -bsf:v h264_mp4toannexb -f h264 "$T/$i.h264"
  ffmpeg -v error -y "${src[@]}" -c:v libx265 -x265-params log-level=error:keyint=45:bframes=2 \
    -f hevc "$T/$i.hevc"
done
cat "$T"/{1,2,3}.h264 > "$DIR/h264-reschange.h264"
cat "$T"/{1,2,3}.hevc > "$DIR/hevc-reschange.hevc"
for f in "$DIR"/h264-reschange.h264 "$DIR"/hevc-reschange.hevc; do
  echo "$f: $(ffprobe -v error -show_entries frame=width,height -of csv=p=0 "$f" | uniq -c | tr '\n' ' ')"
done
