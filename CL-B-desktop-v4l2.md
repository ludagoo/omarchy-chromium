# Proposal: V4L2 video on desktop Linux, behind flags that already exist

This is a design proposal, not one of the decode fixes. Do not send it to Gerrit with them. Do not flip a default. Official Chrome keeps `use_v4l2_codec` off, and VA-API stays the desktop path. Lucas signs the contributor agreement and uploads only after an independent review. Nothing here has been uploaded.

One code change goes with it: the sandbox change in `CL-B1-sandbox-codec-nodes.md` (patch 0007 on `smartroom/upstream-main`). Attach it to the proposal. It makes the broker policy match the devices `V4L2Device` already opens on desktop Linux. On Apple silicon the GPU sandbox does not engage today, so it changes nothing there yet (see below).

## What to ask

Mail one owner of `media/gpu/v4l2`, not both: `frkoenig@chromium.org` or `nhebert@chromium.org`. Mark it as a design, or send it as a review with no behavior change for official Chrome.

Google already chose the shape of this in July 2026. Bug 530450488 (author amazingfate) lets one build contain both VA-API and V4L2. The feature `PreferV4L2VideoAcceleration` picks V4L2 at run time and defaults off. It switches the whole pipeline. It is not our old hybrid, which decoded with VA-API and encoded with V4L2 at the same time.

The run line for a distro build that already passes `use_v4l2_codec=true` is:

```
--enable-features=PreferV4L2VideoAcceleration,AcceleratedVideoDecoder
```

Both features exist. `PreferV4L2VideoAcceleration` defaults off. `AcceleratedVideoDecoder` defaults on only when VA-API is compiled. Leave that default upstream. A V4L2-only build does not turn the decoder on by itself. (Our room package turns it on in its own patch.)

## The sandbox, and what really broke on 148

On desktop Linux, main's `V4L2Device` already looks for codecs at `/dev/videoN` and `/dev/mediaN`. It pairs a decoder with its media controller by `bus_info`, and by driver name when `bus_info` is empty. The GPU process broker policy allows V4L2 nodes only on ChromeOS and Chromecast, and only under the ChromeOS names `/dev/video-decN`, `/dev/media-decN` and `/dev/video-encN`.

On Apple silicon that policy is not what blocks anything today, because the GPU seccomp sandbox does not engage there (Studio, 19 November 2026). Stock Arch Linux ARM Chromium 157, run with every sandbox on, logs `InitializeSandbox() called with multiple threads in process gpu-process`. Its GPU process then runs with `Seccomp: 0`, so the broker list is never applied. That GPU process opened `/dev/video0` and `/dev/media0` with no links. With `--gpu-sandbox-start-early` the sandbox does engage (`Seccomp: 2`), and then the GPU process cannot even load Mesa (`Could not dlopen native EGL: libEGL.so.1: Permission denied`) and exits. That is a separate gap: the pre-sandbox hook preloads GL only for the GPU vendors it knows. It is not part of this proposal.

So the sandbox change (CL-B1) is about correctness for wherever the sandbox does engage. It is not a fix for something Apple silicon users hit today. A desktop V4L2 build should not depend on the GPU sandbox failing to start.

What did break on the room's 148 build (Apple M2 Max, 18 November 2026) was our own patch 011. It made Linux look only under the ChromeOS names, and a udev rule was supposed to create them. Without the links:

- The decoder logged `No V4L2 API found for profile: h264 high`.
- The encoder list was empty.
- In a Zoom Meeting SDK call, WebRTC's H.264 receiver got `NullVideoDecoder` and decoded 0 frames. There was no software picture either.

The same build, with the links made by hand, decoded three inbound 320x180 H.264 streams on `V4L2VideoDecoder` with 0 dropped, at about 0.9 ms per frame. It encoded the 640x360 layer on `V4L2VideoEncodeAccelerator`.

Main and 157 do not have patch 011, so they find `/dev/video0` without links. That is one more reason not to send 011.

Stock 157 on the Studio also shows what main is missing (12 clips, `AcceleratedVideoDecoder` on). H.264 initializes V4L2 in frame-based mode, AVD only offers slice-based, so every H.264 clip falls back to FFmpeg at 53% CPU (1080p) and 107% (2160p). HEVC starts on `V4L2VideoDecoder`, shows 9 frames, and the kernel logs `avd: Frame processing timed out`, because no slice parameters are sent. VP9 profile 0 plays all 600 frames on V4L2, so main's compressed-header support works on AVD. VP9 profile 2 and HEVC Main 10 show 0 frames. The A changes are what fix those.

## What the change would actually do

1. Keep `use_v4l2_codec` off for official Chrome. Distros that want the decoder already pass it. Raspberry Pi OS, Rockchip boards, Arch Linux ARM and our room build are in that group. This proposal does not ask Google Chrome on x86 to use V4L2. The Vulkan Video encoder work is a different proposal.

2. Let the GPU sandbox allow the codec nodes that really exist (CL-B1). Before the sandbox starts, `FindV4L2CodecDevicePaths()` opens each `/dev/videoN` and keeps it only if all of these hold:
   - it is memory-to-memory;
   - it takes a compressed video format (decoder) or produces one (encoder);
   - that format is not JPEG.

   For each decoder it also keeps the `/dev/mediaN` that `V4L2Device` will pair with it. Exactly those paths are allowed, plus the ChromeOS names, so existing udev rules keep working. Cameras, capture cards and v4l2loopback devices are not memory-to-memory, so they never get into the GPU process. Decoder nodes are added only when accelerated decode is enabled, and encoder nodes only when accelerated encode is. No device-name patch is needed, and no udev rule. Boards that already use `/dev/videoN` (Pi, Rockchip) work unchanged. Where the GPU sandbox does not engage (Apple silicon with Mesa today), the scan only matters later, once it does.

   Do not send our patch 011. It forces the ChromeOS names, and that hides the decoder on every board without the udev rule.

3. Leave the V4L2 encoder ChromeOS-only until an owner asks for it. On main, `media/gpu/v4l2/BUILD.gn` adds `v4l2_video_encode_accelerator.cc` only inside `if (is_chromeos)`, and `gpu_video_encode_accelerator_factory.cc` constructs it only under `BUILDFLAG(IS_CHROMEOS)`. The encoder has no HEVC controls. If an owner wants the encoder on Linux later, the follow-ups are:
   - the CPU-NV12 input path (our 015, rewritten for 158: GBM rejects NV12, so desktop encode reads CPU frames);
   - HEVC controls (our 016).

   Both stay behind `AcceleratedVideoEncoder`, which already defaults off. Do not block the decode fixes on this.

4. The encoder's minimum size is the driver's business. Apple's AVE advertises 320x240 as its smallest frame (`VIDIOC_ENUM_FRAMESIZES`). Chromium respects that. In the Zoom call, the simulcast adapter put the 320x180 layer on OpenH264 and the 640x360 layer on AVE (`SimulcastEncoderAdapter (OpenH264, V4L2VideoEncodeAccelerator)`). That fallback is correct behavior. A smaller floor is a driver change.

5. Say who it helps. The stateless decode fixes (slice parameters, DPB flags, reference lists, the held capture buffer, P010, the format probe, HEVC slice parameters) help kernels whose stateless decoder is slice-based. That is Apple's AVD on Asahi, and the usual hantro, cedrus and Rockchip stateless drivers when they advertise slice mode. Raspberry Pi OS Chromium 151 and later uses upstream's stateful decoder (`bcm2835-codec` on `/dev/videoN`), which those fixes do not touch. The sandbox change matters to every one of them wherever their GPU sandbox engages.

## What stays out

- Do not default `AcceleratedVideoDecoder` on for a V4L2-only build upstream.
- Do not spread encoder sessions across nodes inside Chromium. Our cap of two sessions per apple-ave node is a driver fact, not a generic Chromium fix.
- Do not put the Arch API key, the AUTHORS line or the `Assisted-by` trailer into this proposal. AUTHORS is a separate first-patch decision once Lucas picks the email on the agreement.
- Do not open an issue. The July bug is the existing discussion. A design mail to one owner is enough.

## Software fallback

When the V4L2 decoder is missing or fails to start, a call must still show video, decoded in software. On 148 it did not, as described above. Whether main and 158 fall back is tested on the Studio with `tests/sr-webrtc.sh`, by hiding the decoder from launch and by hiding it after the GPU process started. The result goes here.
