# CL A5: media/gpu/v4l2: Decode multi-slice H.264 pictures on slice-based devices

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0006-media-gpu-v4l2-Decode-multi-slice-H.264-pictures-on-.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: On top of A4.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/v4l2_decode_surface.cc                  |  36 ++++++----
    media/gpu/v4l2/v4l2_decode_surface.h                   |   9 +++
    media/gpu/v4l2/v4l2_decode_surface_handler.h           |  15 ++++
    media/gpu/v4l2/v4l2_h264_slice.cc                      |   6 ++
    media/gpu/v4l2/v4l2_h264_slice.h                       |   7 ++
    media/gpu/v4l2/v4l2_h264_slice_unittest.cc             |   7 ++
    media/gpu/v4l2/v4l2_queue.cc                           |  14 ++++
    media/gpu/v4l2/v4l2_queue.h                            |   9 +++
    media/gpu/v4l2/v4l2_video_decoder_backend_stateless.cc | 116 ++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder_backend_stateless.h  |  10 +++
    media/gpu/v4l2/v4l2_video_decoder_delegate_h264.cc     | 143 ++++++++++++++++++++++++++++++++++---

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Decode multi-slice H.264 pictures on slice-based devices

A slice-based stateless decoder takes one slice per media request. The
V4L2 stateless API decodes a picture made of several slices by sending
each slice in its own request and setting
V4L2_BUF_FLAG_M2M_HOLD_CAPTURE_BUF on every bitstream buffer but the
last, so all slices write the same CAPTURE buffer. Chromium does not
use that flag, so after the previous change a multi-slice picture on a
slice-based device fails. Encoders produce such pictures when asked
for several slices or a maximum slice size (x264 --slices,
--slice-max-size), which real-time senders use.

For a slice-based device the delegate now keeps every slice of the
picture (bytes, slice parameters, prediction weights). At SubmitDecode:
- one slice: the single-request path is used, as before;
- several slices: each slice except the last is queued by
  V4L2DecodeSurfaceHandler::SubmitHeldSlice() on its own request with
  SPS, PPS, scaling matrix, decode parameters and its slice
  parameters, and with HOLD_CAPTURE_BUF set. The CAPTURE buffer is
  queued with the first slice only. The last slice goes on the
  picture's own request, which releases the CAPTURE buffer.

SubmitHeldSlice() waits until the driver returns the held bitstream
buffer, so the next slice can reuse one; the CAPTURE buffer stays
queued. The order of the queue calls follows libva-v4l2-request.

Whether the OUTPUT queue supports the flag is read with
VIDIOC_CREATE_BUFS(count = 0) after S_FMT, because a driver may only
advertise V4L2_BUF_CAP_SUPPORTS_M2M_HOLD_CAPTURE_BUF for the selected
coded format. If it does not, a multi-slice picture fails as before.
Frame-based devices and single-slice pictures do not change.

Bug: None
Test: media_unittests --gtest_filter=V4L2H264SliceTest.*
Test: H.264 High 1080p clips with 4 slices and with 6 to 29 slices
      per picture (x264) on Apple AVD (Linux arm64): every picture
      decodes on V4L2VideoDecoder; before, multi-slice pictures were
      rejected and playback fell back to software
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2H264SliceTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (multi-slice branch): 4-slice clip 120 frames, 6 dropped; 6-29 slices per picture, 120 frames, 8 dropped (the video element's count at the end of a 4 s clip); hold_capture=1 capabilities=253, only after S_FMT. A WebRTC loopback (1280x720, V4L2VideoDecoder, 268 frames, 0 dropped) did not use this path: OpenH264 sent one slice per picture.

## Results on main

Unit: `media_unittests --gtest_filter='*V4L2*' --single-process-tests`: 29 of 29 passed (results/main-media_unittests-v4l2.txt). `v4l2_unittest`: its 7 tests are skipped on this platform (ChromeOS flat decoder and minigbm tests), none failed. Playback: 4 slices per picture, 120 of 120 frames (7 dropped); 6 to 29 slices per picture, 120 of 120 (9 dropped), both on `V4L2VideoDecoder`. The log shows `hold_capture=1 capabilities=253` and `Submitting 4 H.264 slices, holding the capture buffer until the last`. For comparison, stock Arch Linux ARM Chromium 157.0.8103.78 on the same machine and flags: both clips on `FFmpegVideoDecoder`.
