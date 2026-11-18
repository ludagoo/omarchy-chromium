# CL A2: media/gpu/v4l2: Size the stateless coded format before probing it

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `upstream/0002-coded-size-probe.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Independent of the others.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/v4l2_utils.cc          | 33 +++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_utils.h           | 14 ++++++++++++++
    media/gpu/v4l2/v4l2_utils_unittest.cc | 35 +++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder.cc  | 16 ++++++++++------

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Size the stateless coded format before probing it

SetupInputFormat() calls S_FMT on the OUTPUT (coded) queue with an
empty size. A stateless driver cannot parse the size from the stream,
so it keeps its minimum, 64x64 on some drivers. SetExtCtrlsInit() then
sends an H.264 SPS for the real picture to make the driver list its
CAPTURE formats, and the driver rejects that SPS as larger than the
coded format. No CAPTURE format is reported and decoder init fails.

The probe SPS also had no macroblock size and no frame_mbs_only_flag.
A driver that validates the SPS against the coded format, or that does
not decode interlaced streams, refused it for the same reason.

Pass the picture size to S_FMT for the stateless coded formats only,
and fill the probe SPS from that size and mark it progressive. The
first real frame still sends the SPS the parser read. Stateful
decoders parse the size themselves and keep the empty size.

Bug: None
Test: media_unittests --gtest_filter=V4L2UtilsTest.*
Test: H.264 playback on a stateless decoder whose minimum coded size
      is 64x64 (Apple AVD, Linux arm64); init failed before
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2UtilsTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (patch 018): AVD keeps a 64x64 coded format without it, rejects the probe SPS, lists no CAPTURE format, and decoder init fails.

## Results on main

Pending: the Studio build of `smartroom/v4l2-test` (`out/v4l2-a`).
