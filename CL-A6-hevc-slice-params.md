# CL A6: media/gpu/v4l2: Send HEVC slice parameters to stateless decoders

Prepared, not uploaded. Lucas uploads it himself after the contributor
agreement is on file.

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/0007-media-gpu-v4l2-Send-HEVC-slice-parameters-to-statele.patch`.
- Order: Independent of the H.264 changes (separate delegate).
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org` (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/BUILD.gn                            |   5 +
    media/gpu/v4l2/v4l2_hevc_slice.cc                  | 231 +++++++++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_hevc_slice.h                   |  46 ++++++++
    media/gpu/v4l2/v4l2_hevc_slice_unittest.cc         | 147 ++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_video_decoder_delegate_h265.cc | 116 +++++++++++++++++++--
    media/gpu/v4l2/v4l2_video_decoder_delegate_h265.h  |   5 +

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Replace the `AI-DISCLOSURE-PLACEHOLDER` line with your own sentence (drafts are
in the job notes) and the bug placeholder with the tracking bug.

```
media/gpu/v4l2: Send HEVC slice parameters to stateless decoders

The V4L2 HEVC delegate never sets V4L2_CID_STATELESS_HEVC_SLICE_PARAMS
and always prepends a 3-byte start code. A decoder that needs the
slice header fields (slice type, QP deltas, reference indices,
prediction weights, offset of the slice data) cannot decode without
them, and a decoder that wants V4L2_STATELESS_HEVC_START_CODE_NONE gets
a start code it does not expect. Apple's AVD needs both.

Query once whether the driver exposes the slice-parameters control and
which start code it wants. When the control exists, fill one
v4l2_ctrl_hevc_slice_params per slice and set the array on the
picture's request. data_byte_offset counts the emulation-prevention
bytes of the slice header and the start code, because it is an offset
into the submitted bytes. Reference indices name slots of the DPB array
sent with the decode parameters. Chroma offsets are derived from the
coded delta and the chroma weight (H.265 7-56), as the VA-API delegate
does, and a value that does not fit the 8-bit uAPI field fails the
slice. HEVC stays one request per picture.

Drivers that change: every driver that exposes the slice-parameters
control now receives it. In mainline that is rkvdec, cedrus and the visl
test driver as well as AVD; none of them was tested. Hantro and MediaTek
do not expose it and are unchanged. A slice whose reference is not in
the DPB now fails the picture on those drivers, where before the driver
was left to conceal.

Limits: num_entry_point_offsets is always 0 and
V4L2_CID_STATELESS_HEVC_ENTRY_POINT_OFFSETS is not sent, because the
parser does not keep the offsets. A driver that needs them for tiles or
wavefront parallel processing (cedrus; AVD for tiles) will decode such
streams wrongly. A driver whose HEVC decode mode is SLICE_BASED
(cedrus) still gets the whole picture in one request, as before. A
stream that changes resolution mid-stream (tested: 360p to 720p) stops
with a decode error at the change on AVD; the cause is not known and
this change does not address it. Tested on Apple AVD only (Linux
arm64).

AI-DISCLOSURE-PLACEHOLDER: replace with Lucas's own sentence.

Bug: TRACKING-BUG-PLACEHOLDER
Test: media_unittests --gtest_filter=V4L2HevcSliceTest.*
Test: HEVC 8- and 10-bit clips incl. a weighted-prediction fade on AVD; matches FFmpeg
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2HevcSliceTest.*'` (needs `use_v4l2_codec=true`; no device needed).
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

- A6: every HEVC clip plays, including the weighted-prediction fade. 135 of its slices carry explicit chroma weights (deltas from -127 up) with every coded chroma offset delta 0, so the offset the driver gets comes entirely from the H.265 7-56 derivation; sending the coded delta, as before this round, would send 0.

- Picture (NV12 readback): HEVC 1080p frame 581, 0 off; fade frames 5, 27 and 134, 0 off (FFmpeg numbers the first two 4 and 25).
