#!/bin/bash
# Makes the weighted-prediction test clips in DIR (default .):
#   hevc-fade-1080p30.mp4  x265, colour fades (chroma weighted prediction)
#   h264-fade-1080p30.mp4  x264, same source (weighted P frames)
# The source fades a moving test pattern from black, to a solid colour and
# back, so that chroma, not only luma, changes in the fades. x265 prints the
# share of weighted P frames for luma (Y) and chroma (UV) at the end.
set -eu
DIR=${1:-.}
FC="[0]split=3[a][b][c];\
[a]trim=0:2,setpts=PTS-STARTPTS,fade=t=in:st=0:d=1.5[a1];\
[b]trim=2:4,setpts=PTS-STARTPTS,fade=t=out:st=0.3:d=1.5:color=0x3060c0[b1];\
[c]trim=4:6,setpts=PTS-STARTPTS,fade=t=in:st=0:d=1.5:color=0x3060c0[c1];\
[a1][b1][c1]concat=n=3,format=yuv420p"
ffmpeg -v error -y -f lavfi -i testsrc2=size=1920x1080:rate=30:duration=6 \
  -filter_complex "$FC" -f yuv4mpegpipe "$DIR/fade-src.y4m"
x265 --input "$DIR/fade-src.y4m" --preset medium --crf 24 --keyint 60 --bframes 3 \
  --weightp --weightb --output "$DIR/hevc-fade-1080p30.hevc" 2>&1 | grep -i -E "weight|encoded"
ffmpeg -v error -y -r 30 -i "$DIR/hevc-fade-1080p30.hevc" -c copy -tag:v hvc1 "$DIR/hevc-fade-1080p30.mp4"
x264 --preset medium --crf 22 --keyint 60 --weightp 2 --bframes 3 \
  -o "$DIR/h264-fade-1080p30.mp4" "$DIR/fade-src.y4m" 2>&1 | grep -i -E "weight|encoded"
rm -f "$DIR/fade-src.y4m" "$DIR/hevc-fade-1080p30.hevc"
ls -la "$DIR"/*-fade-1080p30.mp4
