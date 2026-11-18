# Proposal: V4L2 video on desktop Linux, behind flags that already exist

This is not a code change in the first upload. Do not send it to Gerrit with the decode fixes. Do not flip a default. Official Chrome keeps `use_v4l2_codec` off, and VA-API stays the desktop path. Lucas signs the contributor agreement and uploads only after an independent review. Nothing here has been uploaded.

## What to ask

Mail one owner of `media/gpu/v4l2`, not both: `frkoenig@chromium.org` or `nhebert@chromium.org`. Mark it as a design, or send it as a review with no behavior change for official Chrome.

Google already chose the shape of this in July 2026. Bug 530450488 (author amazingfate) lets one build contain both VA-API and V4L2. The feature `PreferV4L2VideoAcceleration` picks V4L2 at run time and defaults off. It switches the whole pipeline. It is not our hybrid, which decoded with VA-API and encoded with V4L2 at the same time.

The run line for a distro build that already passes `use_v4l2_codec=true` is:

```
--enable-features=PreferV4L2VideoAcceleration,AcceleratedVideoDecoder
```

Both features exist. `PreferV4L2VideoAcceleration` defaults off. `AcceleratedVideoDecoder` defaults on only when VA-API is compiled. Leave that default. A V4L2-only build does not turn the decoder on by itself.

## What the change would actually do

1. Keep `use_v4l2_codec` off for official Chrome. Distros that want the decoder already pass it. Raspberry Pi OS, Rockchip boards, and our room build are in that group. This proposal does not ask Google Chrome on x86 to use V4L2. The Vulkan Video encoder work is a different proposal.

2. On Linux, when the binary was built with V4L2 and the accelerated-video feature is on, call `AddV4L2GpuPermissions` the way ChromeOS does. That allows `/dev/video-decN`, `/dev/media-decN`, and `/dev/video-encN`. It does not allow `/dev/videoN`, so a camera node stays out of the GPU process. Today desktop Linux never calls that function, so a sandboxed GPU process cannot open the codec even when the rest of the code is compiled.

3. Teach the non-ChromeOS device lookup to try `/dev/video-decN` and `/dev/media-decN` first, then `/dev/videoN` and `/dev/mediaN`. Do not send our patch 011 as written. That patch forces the ChromeOS names. The Pi and Rockchip use `/dev/videoN`. A lookup that only checks the ChromeOS names would hide their decoder. A udev rule in the distro package can publish the ChromeOS names where the sandbox is on. Our room package ships `chromium-v4l2.rules` for that. The rule is packaging, not a Chromium change. Hand-made links disappear on reboot.

4. Leave the V4L2 encoder ChromeOS-only until an owner asks for it. On this main, `media/gpu/v4l2/BUILD.gn` adds `v4l2_video_encode_accelerator.cc` only inside `if (is_chromeos)`. `gpu_video_encode_accelerator_factory.cc` constructs `V4L2VideoEncodeAccelerator` only under `BUILDFLAG(IS_CHROMEOS)`. The encoder file has no HEVC controls. If an owner wants the encoder on Linux later, the follow-ups are the CPU-NV12 input path (our 015: GBM rejects NV12, so desktop encode uses shared-memory NV12) and HEVC controls (our 016), still behind `AcceleratedVideoEncoder`, which already defaults off. Do not block the seven decode fixes on this.

5. Say who it helps. The stateless decode fixes (slice parameters, DPB flags, reference lists, the held capture buffer, P010, the format probe, HEVC slice parameters) help kernels whose stateless decoder is slice-based. That is Apple's AVD on Asahi, and the usual hantro, cedrus, and Rockchip stateless drivers when they advertise slice mode. Raspberry Pi OS Chromium 151 and later uses upstream's stateful decoder (`bcm2835-codec` on `/dev/videoN`). Those fixes do not run on that path. Arch and Omarchy on Snapdragon use the stateful Venus driver and stay on VA-API unless someone turns the flags on.

## What stays out

- Do not default `AcceleratedVideoDecoder` on for a V4L2-only build.
- Do not spread encoder sessions across nodes inside Chromium. Our cap of two sessions per apple-ave node is a driver fact, not a generic Chromium fix.
- Do not put the Arch API key, the AUTHORS line, or the `Assisted-by` trailer into this proposal. AUTHORS is a separate first-patch decision once Lucas picks the email on the agreement.
- Do not open an issue. The July bug is the existing discussion. A design mail to one owner is enough.
