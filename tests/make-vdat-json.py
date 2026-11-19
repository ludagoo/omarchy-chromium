#!/usr/bin/env python3
"""Makes input for video_decode_accelerator_tests from a clip.

Usage: make-vdat-json.py CLIP OUTDIR

Writes OUTDIR/NAME.{h264,hevc,ivf} (the elementary stream) and NAME.*.json
with the profile, size, frame rate, frame count and one MD5 per frame. The
MD5s are FFmpeg's software decode in I420 (8-bit) or 10-bit little-endian
I420, the formats the test's MD5 validator converts to.
"""
import json
import os
import subprocess
import sys

clip, outdir = sys.argv[1], sys.argv[2]
probe = json.loads(subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
     "stream=codec_name,profile,width,height,r_frame_rate,pix_fmt", "-of", "json", clip],
    capture_output=True, text=True, check=True).stdout)["streams"][0]
codec, prof, pix = probe["codec_name"], probe.get("profile", ""), probe["pix_fmt"]
ten_bit = "10" in pix
num, den = (int(x) for x in probe["r_frame_rate"].split("/"))
name = os.path.splitext(os.path.basename(clip))[0]
if codec == "h264":
    ext, bsf, fmt = "h264", "h264_mp4toannexb", "h264"
    profile = {"High": "H264PROFILE_HIGH", "Main": "H264PROFILE_MAIN"}.get(
        prof, "H264PROFILE_BASELINE" if "Baseline" in prof else "H264PROFILE_HIGH")
elif codec == "hevc":
    ext, bsf, fmt = "hevc", "hevc_mp4toannexb", "hevc"
    profile = "HEVCPROFILE_MAIN10" if ten_bit else "HEVCPROFILE_MAIN"
elif codec == "vp9":
    ext, bsf, fmt = "ivf", None, "ivf"
    profile = "VP9PROFILE_PROFILE2" if ten_bit else "VP9PROFILE_PROFILE0"
else:
    sys.exit("unsupported codec " + codec)
stream = os.path.join(outdir, f"{name}.{ext}")
cmd = ["ffmpeg", "-v", "error", "-y", "-i", clip, "-map", "0:v:0", "-c", "copy"]
if bsf:
    cmd += ["-bsf:v", bsf]
subprocess.run(cmd + ["-f", fmt, stream], check=True)
md5 = subprocess.run(["ffmpeg", "-v", "error", "-i", stream, "-noautoscale", "-f",
                      "framemd5", "-pix_fmt", "yuv420p10le" if ten_bit else "yuv420p", "-"],
                     capture_output=True, text=True, check=True).stdout
sums = [l.split(",")[-1].strip() for l in md5.splitlines() if l and not l.startswith("#")]
meta = {"profile": profile, "bit_depth": 10 if ten_bit else 8, "width": probe["width"],
        "height": probe["height"], "frame_rate": round(num / den), "num_frames": len(sums),
        "md5_checksums": sums}
json.dump(meta, open(stream + ".json", "w"), indent=2)
print(stream, profile, len(sums), "frames")
