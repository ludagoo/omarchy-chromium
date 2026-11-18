# Proposal: V4L2 video on desktop Linux, behind flags that already exist

This is a design proposal, not one of the decode fixes. Do not send it to Gerrit with them. Do not flip a default. Official Chrome keeps `use_v4l2_codec` off, and VA-API stays the desktop path. Lucas signs the contributor agreement and uploads only after an independent review. Nothing here has been uploaded.

One code change goes with it: the sandbox change in `CL-B1-sandbox-codec-nodes.md` (patch 0007 on `smartroom/upstream-main`). Attach it to the proposal as the concrete first step.

## What to ask

Mail one owner of `media/gpu/v4l2`, not both: `frkoenig@chromium.org` or `nhebert@chromium.org`. Mark it as a design, or send it as a review with no behavior change for official Chrome.

Google already chose the shape of this in July 2026. Bug 530450488 (author amazingfate) lets one build contain both VA-API and V4L2. The feature `PreferV4L2VideoAcceleration` picks V4L2 at run time and defaults off. It switches the whole pipeline. It is not our old hybrid, which decoded with VA-API and encoded with V4L2 at the same time.

The run line for a distro build that already passes `use_v4l2_codec=true` is:

```
--enable-features=PreferV4L2VideoAcceleration,AcceleratedVideoDecoder
```

Both features exist. `PreferV4L2VideoAcceleration` defaults off. `AcceleratedVideoDecoder` defaults on only when VA-API is compiled. Leave that default upstream. A V4L2-only build does not turn the decoder on by itself. (Our room package turns it on in its own patch.)

## Why the sandbox is the blocker

On desktop Linux, main's `V4L2Device` already looks for codecs at `/dev/videoN` and `/dev/mediaN`. It pairs a decoder with its media controller by `bus_info`, and by driver name when `bus_info` is empty. The GPU process broker, however, allows V4L2 nodes only on ChromeOS and Chromecast, and only under the ChromeOS names `/dev/video-decN`, `/dev/media-decN` and `/dev/video-encN`. So once the GPU sandbox is on, a desktop build with `use_v4l2_codec=true` finds nothing.

What that looks like on a real machine (Apple M2 Max, our 148 room build, 18 November 2026). That build had a patch (our 011) that made Linux look only under the ChromeOS names, and a udev rule was supposed to create them. After a reboot the rule was not installed and the links were gone:

- The decoder logged `No V4L2 API found for profile: h264 high`.
- The encoder list was empty.
- In a Zoom Meeting SDK call, WebRTC's H.264 receiver got `NullVideoDecoder` and decoded 0 frames. There was no software picture either.

The same build, with the links made by hand, decoded three inbound 320x180 H.264 streams on `V4L2VideoDecoder` with 0 dropped, at about 0.9 ms per frame. It encoded the 640x360 layer on `V4L2VideoEncodeAccelerator`.

Distributions work around the sandbox with `--disable-gpu-sandbox`, which drops the sandbox for the whole GPU process, or with links plus a patch like our 011. Both are fragile, and the first is a security cost.

## What the change would actually do

1. Keep `use_v4l2_codec` off for official Chrome. Distros that want the decoder already pass it. Raspberry Pi OS, Rockchip boards, Arch Linux ARM and our room build are in that group. This proposal does not ask Google Chrome on x86 to use V4L2. The Vulkan Video encoder work is a different proposal.

2. Let the GPU sandbox allow the codec nodes that really exist (CL-B1). Before the sandbox starts, `FindV4L2CodecDevicePaths()` opens each `/dev/videoN` and keeps it only if all of these hold:
   - it is memory-to-memory;
   - it takes a compressed video format (decoder) or produces one (encoder);
   - that format is not JPEG.

   For each decoder it also keeps the `/dev/mediaN` that `V4L2Device` will pair with it. Exactly those paths are allowed, plus the ChromeOS names, so existing udev rules keep working. Cameras, capture cards and v4l2loopback devices are not memory-to-memory, so they never get into the GPU process. Decoder nodes are added only when accelerated decode is enabled, and encoder nodes only when accelerated encode is. No device-name patch is needed, and no udev rule. Boards that already use `/dev/videoN` (Pi, Rockchip) work unchanged.

   Do not send our patch 011. It forces the ChromeOS names, and that hides the decoder on every board without the udev rule.

3. Leave the V4L2 encoder ChromeOS-only until an owner asks for it. On main, `media/gpu/v4l2/BUILD.gn` adds `v4l2_video_encode_accelerator.cc` only inside `if (is_chromeos)`, and `gpu_video_encode_accelerator_factory.cc` constructs it only under `BUILDFLAG(IS_CHROMEOS)`. The encoder has no HEVC controls. If an owner wants the encoder on Linux later, the follow-ups are:
   - the CPU-NV12 input path (our 015, rewritten for 158: GBM rejects NV12, so desktop encode reads CPU frames);
   - HEVC controls (our 016).

   Both stay behind `AcceleratedVideoEncoder`, which already defaults off. Do not block the decode fixes on this.

4. The encoder's minimum size is the driver's business. Apple's AVE advertises 320x240 as its smallest frame (`VIDIOC_ENUM_FRAMESIZES`). Chromium respects that. In the Zoom call, the simulcast adapter put the 320x180 layer on OpenH264 and the 640x360 layer on AVE (`SimulcastEncoderAdapter (OpenH264, V4L2VideoEncodeAccelerator)`). That fallback is correct behavior. A smaller floor is a driver change.

5. Say who it helps. The stateless decode fixes (slice parameters, DPB flags, reference lists, the held capture buffer, P010, the format probe, HEVC slice parameters) help kernels whose stateless decoder is slice-based. That is Apple's AVD on Asahi, and the usual hantro, cedrus and Rockchip stateless drivers when they advertise slice mode. Raspberry Pi OS Chromium 151 and later uses upstream's stateful decoder (`bcm2835-codec` on `/dev/videoN`), which those fixes do not touch. The sandbox change helps every one of them.

## What stays out

- Do not default `AcceleratedVideoDecoder` on for a V4L2-only build upstream.
- Do not spread encoder sessions across nodes inside Chromium. Our cap of two sessions per apple-ave node is a driver fact, not a generic Chromium fix.
- Do not put the Arch API key, the AUTHORS line or the `Assisted-by` trailer into this proposal. AUTHORS is a separate first-patch decision once Lucas picks the email on the agreement.
- Do not open an issue. The July bug is the existing discussion. A design mail to one owner is enough.

## Software fallback

When the V4L2 decoder is missing or fails to start, a call must still show video, decoded in software. On 148 it did not, as described above. Whether main and 158 fall back is tested on the Studio with `tests/sr-webrtc.sh`, by hiding the decoder from launch and by hiding it after the GPU process started. The result goes here.
