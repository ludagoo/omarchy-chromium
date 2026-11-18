# CL B1: content/gpu: Allow V4L2 codec nodes in the desktop Linux GPU sandbox

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `upstream/0007-sandbox-codec-nodes.patch` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `smartroom/v4l2-b` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: Independent of the A changes; send it with the design proposal (CL-B-desktop-v4l2.md), not with the decode fixes.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`). `content/common` needs its own owner: run `git cl owners`.

Files:

    content/common/gpu_pre_sandbox_hook_linux.cc |  23 +++++
    media/gpu/v4l2/BUILD.gn                      |   3 +
    media/gpu/v4l2/v4l2_codec_nodes.cc           | 212 +++++++++++++++++++++++++++++++++++++++++++++++
    media/gpu/v4l2/v4l2_codec_nodes.h            |  70 ++++++++++++++++
    media/gpu/v4l2/v4l2_codec_nodes_unittest.cc  |  82 ++++++++++++++++++

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
content/gpu: Allow V4L2 codec nodes in the desktop Linux GPU sandbox

A Linux build with use_v4l2_codec=true compiles the V4L2 decoder, and
on Linux V4L2Device looks for it at /dev/videoN and /dev/mediaN. The
GPU process broker, however, allows V4L2 nodes only on ChromeOS and
Chromecast, and only under the ChromeOS names (/dev/video-decN,
/dev/media-decN, /dev/video-encN). With the GPU sandbox on, a desktop
build therefore finds no V4L2 device: "No V4L2 API found for profile:
h264 high" and an empty encoder profile list.

Distributions work around this with --disable-gpu-sandbox, or with a
udev rule that creates the ChromeOS names plus a patch that makes Linux
look only for those. The second one fails quietly whenever the links
are missing (rule not installed, or a hand-made link gone after a
reboot). On Apple M2 Max with such a build, a WebRTC call then had no
hardware decoder for H.264 and showed no remote video.

Find the codec nodes before the sandbox starts and allow exactly
those. FindV4L2CodecDevicePaths() lists /dev/videoN nodes that are
memory-to-memory and take (decoder) or produce (encoder) a compressed
video format, and for decoders the /dev/mediaN controller with the
same bus_info (or driver, when bus_info is empty), which is how
V4L2Device pairs them for the request API. Cameras, capture cards and
v4l2loopback nodes are not memory-to-memory and are never allowed;
JPEG codecs and image processors are not video codecs. The ChromeOS
names are allowed as well, so existing udev rules keep working.
Decoder nodes are only allowed when accelerated video decode is
enabled, encoder nodes only when accelerated video encode is.

Nothing changes for builds without use_v4l2_codec (official Chrome),
for ChromeOS, or for Chromecast. With use_vaapi and use_v4l2_codec
both set, the scan finds nothing on a machine without V4L2 codecs.

Bug: None
Test: media_unittests --gtest_filter=V4L2CodecNodesTest.*
Test: Linux arm64 (Apple M2 Max, kernel 7.2), GPU sandbox on, no
      /dev/video-dec* or /dev/video-enc* links: H.264 plays on
      V4L2VideoDecoder; the v4l2loopback cameras are not opened by
      the GPU process
```

## Tests

- Unit: `media_unittests --gtest_filter='V4L2CodecNodesTest.*'` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

See CL-B-desktop-v4l2.md for the failures this removes (148 build and the supervisor's Zoom check without the udev links).

## Results on main

Pending: the Studio build of `smartroom/v4l2-test` (`out/v4l2-a`).
