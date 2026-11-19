# CL A4: media/gpu/v4l2: Submit only reference pictures in a slice-based H.264 DPB

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0005-media-gpu-v4l2-Submit-only-reference-pictures-in-a-s.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: On top of A3.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/v4l2_h264_slice.cc                  | 15 +++++++++++++++
    media/gpu/v4l2/v4l2_h264_slice.h                   |  7 +++++++
    media/gpu/v4l2/v4l2_h264_slice_unittest.cc         | 19 +++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder_delegate_h264.cc | 13 ++++++++++---

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Submit only reference pictures in a slice-based H.264 DPB

H264DPBToV4L2DPB() packs every picture of the H264DPB into
v4l2_ctrl_h264_decode_params.dpb[], including non-reference pictures
that are only waiting to be output. Those are marked VALID without
ACTIVE.

On a slice-based device the reference lists in the slice parameters
are indices into that array. A driver that builds its reference table
from the VALID entries (Apple AVD does) then has more entries than
references, and a slice index points at the wrong picture or past the
table. The stream decodes with corrupted inter frames or the request
is rejected.

In slice-based mode, leave non-reference pictures out of the array, so
the array is exactly the reference set and each entry is VALID and
ACTIVE. Frame-based devices do not use the slot numbers and keep
receiving every picture, ACTIVE only for references, as before.

Bug: None
Test: media_unittests --gtest_filter=V4L2H264SliceTest.*
Test: H.264 High 1080p and 2160p clips on Apple AVD (Linux arm64):
      play to the end on V4L2VideoDecoder; before, the decoder hung
      once a non-reference picture kept for display sat in front of a
      reference in the DPB
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2H264SliceTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (2d816dd): all eight test clips stay on V4L2VideoDecoder to the end (600 frames), with no AVD watchdog in the kernel log. Before, a non-reference picture kept for display could sit in front of a reference; AVD sizes its table from the ACTIVE count, the slice's index fell off the end, and the decoder hung.

## Results on main

Unit: `media_unittests --gtest_filter='*V4L2*' --single-process-tests`: 29 of 29 passed (results/main-media_unittests-v4l2.txt). `v4l2_unittest`: its 7 tests are skipped on this platform (ChromeOS flat decoder and minigbm tests), none failed. Playback: all four H.264 clips play to the end on `V4L2VideoDecoder`, with no `avd` lines in the kernel log.
