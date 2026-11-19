# CL A1: media/gpu/v4l2: Give single-buffer P010 a second color plane

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `upstream/0002-p010-plane.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Independent of the others.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/v4l2_utils.cc          |  5 +++--
    media/gpu/v4l2/v4l2_utils_unittest.cc | 25 +++++++++++++++++++++++++

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Give single-buffer P010 a second color plane

V4L2FormatToVideoFrameLayout() derives the UV plane of a one-buffer
format from the Y plane only for V4L2_PIX_FMT_NV12. A driver that
returns V4L2_PIX_FMT_P010 (one buffer, 16-bit samples, interleaved UV
at half height) produced a one-plane layout, so the frame was rejected
and 10-bit H.264, HEVC Main 10 and VP9 profile 2 output could not be
mapped.

P010 has the NV12 shape with 16-bit samples. bytesperline is already
in bytes, so the chroma plane uses the same stride and half the luma
height, exactly like NV12.

Bug: None
Test: media_unittests --gtest_filter=V4L2UtilsTest.*P010*
Test: 10-bit HEVC and VP9 profile 2 playback on a stateless decoder
      that exposes single-buffer P010 (Apple AVD, Linux arm64)
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2UtilsTest.*P010*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (patch 020): HEVC Main 10 and VP9 profile 2 frames map; without it the frame layout has one plane and is rejected.

## Results on main

Pending: the Studio build of `smartroom/v4l2-test` (`out/v4l2-a`).
