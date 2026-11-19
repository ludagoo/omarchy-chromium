# CL A6: media/gpu/v4l2: Send HEVC slice parameters to stateless decoders

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `upstream/0007-hevc-slice-params.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-upstream` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Independent of the H.264 changes (separate delegate).
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/BUILD.gn                            |   5 ++
    media/gpu/v4l2/v4l2_hevc_slice.cc                  | 191 +++++++++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_hevc_slice.h                   |  51 +++++++++++
    media/gpu/v4l2/v4l2_hevc_slice_unittest.cc         |  89 +++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder_delegate_h265.cc | 130 ++++++++++++++++++++++++++--
    media/gpu/v4l2/v4l2_video_decoder_delegate_h265.h  |   5 ++

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
media/gpu/v4l2: Send HEVC slice parameters to stateless decoders

The V4L2 HEVC delegate never sets V4L2_CID_STATELESS_HEVC_SLICE_PARAMS
and always prepends a 3-byte start code. Decoders that only need the
SPS, PPS and decode parameters work that way. A decoder that needs the
slice header fields (slice type, QP deltas, reference indices,
prediction weights, the offset of the slice data) cannot decode
without them, and a decoder that advertises
V4L2_STATELESS_HEVC_START_CODE_NONE gets a start code it does not
expect. Apple's AVD needs both.

Query once whether the driver exposes the slice-parameters control and
which start code it wants. When the control exists, fill one
v4l2_ctrl_hevc_slice_params per slice and set the array on the
picture's request before it is queued. data_byte_offset counts the
emulation-prevention bytes of the slice header and the start code, if
any, because it is an offset into the bytes submitted. Reference
indices name slots of the DPB array sent with the decode parameters.

HEVC stays one request per picture, as the uAPI defines for
FRAME_BASED decode mode. When the driver does not expose the control,
or uses the default Annex-B start code, the submitted data is
unchanged.

Bug: None
Test: media_unittests --gtest_filter=V4L2HevcSliceTest.*
Test: HEVC Main and Main 10 playback on Apple AVD (Linux arm64):
      decodes on V4L2VideoDecoder; before, one frame was shown and the
      driver timed out ("avd: Frame processing timed out")
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2HevcSliceTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

On 148 (patch 017 HEVC part): HEVC Main 1080p/2160p decode on AVD; before, the driver timed out (`avd: Frame processing timed out`).

## Results on main

Unit: `media_unittests --gtest_filter='*V4L2*' --single-process-tests`: 29 of 29 passed (results/main-media_unittests-v4l2.txt). `v4l2_unittest`: its 7 tests are skipped on this platform (ChromeOS flat decoder and minigbm tests), none failed. Playback: HEVC 1080p, 2160p and the 8-bit `hevc10` clip, 600 of 600 frames each on `V4L2VideoDecoder` (36, 31, 34 dropped), and HEVC Main 10, 120 of 120. The log shows `HEVC stateless decode_mode=1 start_code=0 slice_params=1`; no `avd` kernel lines. For comparison, stock Arch Linux ARM Chromium 157.0.8103.78 on the same machine and flags: HEVC starts on `V4L2VideoDecoder`, shows 9 frames, and the kernel logs `avd: Frame processing timed out`.
