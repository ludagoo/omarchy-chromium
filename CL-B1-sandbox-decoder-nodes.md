# CL B1: content/gpu: Allow V4L2 decoder nodes in the desktop Linux GPU sandbox

Prepared, not uploaded. Lucas uploads it himself after the contributor
agreement is on file.

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/on-hold/0008-content-gpu-Allow-V4L2-decoder-nodes-in-the-desktop-.patch`.
- Order: ON HOLD: not part of this upload set. Needs its bug and the design discussion (CL-B-desktop-v4l2.md) first. Applies on top of A0-A6.
- Reviewers: a sandbox owner from `sandbox/linux/OWNERS` (the hook file is `set noparent` to them), plus one of `frkoenig@chromium.org`, `nhebert@chromium.org` (`media/gpu/v4l2/OWNERS`).

Files:

    content/common/gpu_pre_sandbox_hook_linux.cc  |  27 +++++++
    media/gpu/v4l2/BUILD.gn                       |   3 +
    media/gpu/v4l2/v4l2_decoder_nodes.cc          | 187 ++++++++++++++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_decoder_nodes.h           |  59 +++++++++++++++
    media/gpu/v4l2/v4l2_decoder_nodes_unittest.cc |  71 ++++++++++++++++++

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Replace the `AI-DISCLOSURE-PLACEHOLDER` line with your own sentence (drafts are
in the job notes) and the bug placeholder with the tracking bug.

```
content/gpu: Allow V4L2 decoder nodes in the desktop Linux GPU sandbox

A Linux build with use_v4l2_codec=true compiles the V4L2 decoder, and on
Linux V4L2Device opens it at /dev/videoN and /dev/mediaN. The GPU
process broker policy allows V4L2 nodes only on ChromeOS and Chromecast,
and only under the ChromeOS names (/dev/video-decN, /dev/media-decN),
which desktop kernels and udev do not create. Reading the broker policy,
every open of a decoder node would be denied once the GPU sandbox is
engaged, and decode would fall back to software.

On the only machine tested (Apple M2 Max, Asahi Mesa) the GPU seccomp
sandbox does not engage with default flags: GL initialization starts
driver threads first and the sandbox logs "InitializeSandbox() called
with multiple threads". So this change could not be shown to fix a
decode there. It is sent so that a desktop V4L2 build does not depend on
the sandbox failing to start.

When accelerated decode is on and V4L2 is the active Linux decoder
(ActiveLinuxVideoDecoderType()), find the decoder nodes before the
sandbox starts and allow only those: /dev/videoN nodes that are memory-
to-memory, take a compressed video format and produce none, and the
/dev/mediaN controller with the same bus_info (or driver, when bus_info
is empty), which is how V4L2Device pairs them for the request API.
Cameras, capture cards and v4l2loopback nodes are not memory-to-memory
and are never allowed; encoders, JPEG codecs and image processors are
not decoders. The ChromeOS names are not added on desktop: V4L2Device
does not open them there.

Two differences from the ChromeOS rule, which avoids a FileEnumerator on
purpose:
- The list is fixed when the GPU process starts. A decoder that appears
  later is not allowed until the GPU process restarts.
- Nodes are allowed by number. If the decoder driver is unbound while
  the GPU process runs, its number could be reused by another device
  until the GPU process restarts.

Cost: the scan opens every /dev/videoN read-write to ask what it is.
Opening a camera node can wake a USB camera from autosuspend or power
its sensor. It runs only when V4L2 decoding will be used, not in builds
where VA-API is the active backend.

Nothing changes for builds without use_v4l2_codec (official Chrome), for
ChromeOS, or for Chromecast.

AI-DISCLOSURE-PLACEHOLDER: replace with Lucas's own sentence.

Bug: B1-BUG-PLACEHOLDER
Test: media_unittests --gtest_filter=V4L2DecoderNodesTest.*
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2DecoderNodesTest.*'` (needs `use_v4l2_codec=true`; no device needed).
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

- B1: hardware decode works with B1 and every sandbox flag on (`sandbox=1`), and the GPU process held only `/dev/media0` and `/dev/video0`. The GPU seccomp sandbox does not engage on this machine (see the description), so this shows that B1 does not break decode, not that it lets a sandboxed GPU process decode.
