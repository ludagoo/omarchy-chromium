# CL A0: media/gpu/v4l2: Expect the linear modifier in layout tests on Linux

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0001-media-gpu-v4l2-Expect-the-linear-modifier-in-layout-.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Test-only. Send first: A1 extends the same test file.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/BUILD.gn               |  1 +
    media/gpu/v4l2/v4l2_utils_unittest.cc | 30 +++++++++++++++++++++---------

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

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

Bug: None
Test: media_unittests --gtest_filter=V4L2UtilsTest.* (Linux arm64,
      use_v4l2_codec=true): NV12, NV12M and YUV420 failed before
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2UtilsTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

Not from the 148 port. Found when the unit tests first ran on main in a Linux build (19 Nov): the NV12, NV12M and YUV420 layout tests fail because V4L2FormatToVideoFrameLayout() sets DRM_FORMAT_MOD_LINEAR on Linux.

## Results on main

Unit: `media_unittests --gtest_filter='*V4L2*' --single-process-tests`: 29 of 29 passed (results/main-media_unittests-v4l2.txt). `v4l2_unittest`: its 7 tests are skipped on this platform (ChromeOS flat decoder and minigbm tests), none failed. Before this change, 4 of the 11 `V4L2UtilsTest` tests failed (NV12, NV12M, YUV420, and the new P010 test), each only on the modifier: `0x0` (linear) against an expected `0xffffffffffffff`.
