# CL A3: media/gpu/v4l2: Support slice-based stateless H.264 decoders

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0004-media-gpu-v4l2-Support-slice-based-stateless-H.264-d.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Needs nothing below it. A4 and A5 build on it.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/BUILD.gn                                |   3 +
    media/gpu/v4l2/v4l2_h264_slice.cc                      | 199 +++++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_h264_slice.h                       |  69 +++++++++++++
    media/gpu/v4l2/v4l2_h264_slice_unittest.cc             | 121 ++++++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder_backend_stateless.cc |  10 ++
    media/gpu/v4l2/v4l2_video_decoder_delegate_h264.cc     | 149 +++++++++++++++++++++++++--
    media/gpu/v4l2/v4l2_video_decoder_delegate_h264.h      |   3 +

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Support slice-based stateless H.264 decoders

The V4L2 H.264 delegate always sets V4L2_CID_STATELESS_H264_DECODE_MODE
to FRAME_BASED, always prepends a 3-byte start code, and never sends
V4L2_CID_STATELESS_H264_SLICE_PARAMS. That matches the frame-based
ChromeOS decoders, and also Hantro, rkvdec, MediaTek and Tegra on
mainline. A driver whose only mode is SLICE_BASED, such as cedrus and
Apple's AVD, rejects the request and nothing decodes.

Ask the device once which decode modes it offers (VIDIOC_QUERYMENU)
and which start code it defaults to. A device that offers FRAME_BASED
keeps it, even when it also offers SLICE_BASED, so nothing changes for
it: the DPB and decode parameters are filled as before, the start code
is its Annex-B default, and DECODE_MODE is still sent with each
request.

For a device whose only mode is SLICE_BASED:
- RequiresRefLists() returns true so H264Decoder builds
  RefPicList0/1.
- Each slice fills v4l2_ctrl_h264_slice_params (and pred weights when
  the PPS uses them). Reference lists name slots in the DPB array
  submitted in the same request. When num_ref_idx_active exceeds the
  pictures available early in a GOP, the spare slots repeat the last
  real reference; the bitstream does not address them, but the driver
  validates every active index.
- DECODE_MODE is left at the driver's default.
- A picture with more than one slice fails for now. Holding the
  CAPTURE buffer across several requests is a follow-up change.

START_CODE_NONE is honored in both modes. A raw NAL is submitted
without trailing zero bytes, which are the next start code's zero_byte
and which a slice-based decoder reads as slice data.

The stateless backend also zeroes up to 64 bytes after the bitstream,
outside bytesused. Some stateless decoders prefetch past the end of the
slice; libva-v4l2-request does the same.

Bug: None
Test: media_unittests --gtest_filter=V4L2H264SliceTest.*
Test: H.264 playback on Apple AVD (slice-based, START_CODE_NONE,
      Linux arm64): decodes on V4L2VideoDecoder; before, every request
      was rejected
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2H264SliceTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (patch 017 + 019): H.264 decodes on V4L2VideoDecoder on AVD; before, every request was rejected and the player fell back to FFmpeg. The supervisor's Zoom Meeting SDK check (18 Nov, 148 build with A3-A5, /dev/video-dec0 link made by hand) decoded three inbound 320x180 H.264 streams on V4L2VideoDecoder, 0 dropped, about 0.9 ms per frame.

## Results on main

Unit: `media_unittests --gtest_filter='*V4L2*' --single-process-tests`: 29 of 29 passed (results/main-media_unittests-v4l2.txt). `v4l2_unittest`: its 7 tests are skipped on this platform (ChromeOS flat decoder and minigbm tests), none failed. Playback: H.264 1080p and 2160p, 600 of 600 frames each on `V4L2VideoDecoder` (91 and 34 dropped, 10.6% and 10.0% CPU). The log shows `H.264 stateless decode_mode=0 start_code=0` (slice-based, no start code). For comparison, stock Arch Linux ARM Chromium 157.0.8103.78 on the same machine and flags: every H.264 clip falls back to `FFmpegVideoDecoder`, at 53% CPU (1080p) and 107% (2160p). WebRTC loopback (OpenH264 sender, 1280x720, 15 fps): `ExternalDecoder (V4L2VideoDecoder)`, 269 frames decoded, 0 dropped, receiver CPU 5.3%; told the stream is High (64001f), the same.
