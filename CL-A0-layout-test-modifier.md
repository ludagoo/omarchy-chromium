# CL A0: media/gpu/v4l2: Expect the linear modifier in layout tests on Linux

Prepared, not uploaded. Lucas uploads it himself after the contributor
agreement is on file.

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0001-media-gpu-v4l2-Expect-the-linear-modifier-in-layout-.patch`.
- Order: Test-only, plus the AUTHORS line. Send first: A1 extends the same test file.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org` (`media/gpu/v4l2/OWNERS`).

Files:

    AUTHORS                               |  1 +
    media/gpu/v4l2/BUILD.gn               |  1 +
    media/gpu/v4l2/v4l2_utils_unittest.cc | 30 +++++++++++++++++++++---------

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Replace the `AI-DISCLOSURE-PLACEHOLDER` line with your own sentence (drafts are
in the job notes) and the bug placeholder with the tracking bug.

```
media/gpu/v4l2: Expect the linear modifier in layout tests on Linux

V4L2FormatToVideoFrameLayout() sets DRM_FORMAT_MOD_LINEAR on Linux
(DRM_FORMAT_MOD_MTK_16L_32S_TILE for MM21) and leaves the modifier at
gfx::NativePixmapHandle::kNoModifier on ChromeOS. The NV12, NV12M and
YUV420 layout tests always expect kNoModifier, so they fail in a Linux
build with use_v4l2_codec=true:

  Which is: "... modifier: 0x0)"
  Which is: "... modifier: 0xffffffffffffff)"

Expect the modifier the function sets on the platform under test. No
change to the code under test.

Also add the author to AUTHORS.

AI-DISCLOSURE-PLACEHOLDER: replace with Lucas's own sentence.

Bug: 526240284
Test: media_unittests --gtest_filter=V4L2UtilsTest.* on Linux arm64
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2UtilsTest.*'` (needs `use_v4l2_codec=true`; no device needed).
- Compile: every changed file was compiled with Chromium's own clang and its
  plugins (find-bad-constructs, raw-ptr-plugin, unsafe-buffers) and `-Werror`,
  syntax only, against the build's headers. Not a full bot build; a CQ dry run
  is still the real check.
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play
  video.

## Results

All results come from one build with A0-A6 and the on-hold B1 applied
together on Chromium main `98478f51939a` (Chrome/160.0.8170.0, Linux arm64
release build). The CLs were tested together as one build, not one by one.
The machine is an Apple M2 Max desktop (2023) running Asahi Linux, kernel
7.2, with the AVD decoder at `/dev/video0`. Video was played with
`--enable-features=AcceleratedVideoDecoder`; without it Chromium decodes
in software.

- Unit tests: `media_unittests --gtest_filter='*V4L2*'` ran 28 tests, all
  passed (V4L2DecoderNodesTest 5, V4L2H264SliceTest 6, V4L2HevcSliceTest 4,
  V4L2UtilsTest 10, V4L2VP9HelpersTest 3).
- Playback: every clip below played to the end on `V4L2VideoDecoder`, with
  no AVD kernel errors.

| Clip | Frames | Dropped | CPU |
|---|---|---|---|
| H.264 High 1080p30 (B-frames) | 600 | 92 | 10.3% |
| H.264 High 2160p30 | 600 | 31 | 10.0% |
| H.264 1080p30, 4 slices per picture | 120 | 8 | 2.9% |
| H.264 1080p30, 6 to 29 slices per picture | 120 | 4 | 3.2% |
| H.264 1080p30 fade (weighted prediction) | 180 | 30 | 1.3% |
| HEVC Main 1080p30 | 600 | 34 | 10.6% |
| HEVC Main 2160p30 | 600 | 36 | 11.0% |
| HEVC Main 1080p30 (second clip) | 600 | 27 | 10.9% |
| HEVC Main 10 1080p30 | 120 | 7 | 2.9% |
| HEVC 1080p30 fade (weighted prediction) | 178 | 26 | 3.6% |
| VP9 profile 0 1080p30 | 600 | 27 | 8.4% |
| VP9 profile 0 2160p30 | 600 | 48 | 9.0% |
| VP9 profile 2 1080p30 (two clips) | 600, 120 | 42, 6 | 9.1%, 2.9% |

- Picture check: `video_decode_accelerator_tests` does not run on desktop
  Linux. Its HEVC and VP9 runs crash in the test's own frame wrapper
  ("Unsupported conversion from wrapped DMA buffers to MappableSharedImage
  VideoFrame"), and its H.264 reader feeds one NAL unit per buffer, which
  H264Decoder finishes as a whole picture, so any multi-slice stream fails
  there with every backend. Instead, frames were read back from the
  `<video>` with WebCodecs (`VideoFrame.copyTo`, and through a 2D canvas)
  and compared with FFmpeg's decode of the same frame. Software decode in
  the same build matches FFmpeg bit for bit (NV12) and at 70 to 84 dB
  (canvas). Hardware frames are not bit-identical, because the hardware
  frame path converts them with BT.601 coefficients on the way to RGB.
  So the test is: is every Chromium pixel a fixed function of FFmpeg's YUV
  value at that pixel? A decode error breaks that; a colour conversion
  does not. Per frame, the share of pixels that differ from what their
  FFmpeg value predicts is given below; 0 means the decode matches FFmpeg.
- Known problems found by these tests, all also present without this
  round's changes: 8-bit VP9 decodes to a flat frame (also on unpatched
  main, so not caused by these CLs); seeking an H.264 stream with B-frames
  can hang because the driver-allocated CAPTURE queue has only DPB + 2
  buffers (a separate follow-up patch fixes it); a mid-stream resolution
  change stops with a decode error at the change.

- A0 itself: the 10 `V4L2UtilsTest` tests pass with the linear modifier expected on Linux.
