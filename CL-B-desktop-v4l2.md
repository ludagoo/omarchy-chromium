# Proposal: V4L2 video on desktop Linux, behind flags that already exist

This is a design proposal, not one of the decode fixes. Do not send it to
Gerrit with them. Do not flip a default. Official Chrome keeps
`use_v4l2_codec` off, and VA-API stays the desktop path. Nothing here has been
uploaded.

One code change goes with it: the sandbox change in
`CL-B1-sandbox-decoder-nodes.md` (`patches/on-hold/0008-...patch`, on top of
A0-A6). It is on hold: file its bug and send this proposal first. On Apple
silicon the GPU sandbox does not engage today, so the change could not be
shown to fix anything on the test machine (see below).

## What to ask

File the bug for B1 (component `Internals>Sandbox`, cc
`Internals>Media>Hardware`) and send this proposal with it. The sandbox change
needs a sandbox owner (`sandbox/linux/OWNERS`); the V4L2 side needs one owner
of `media/gpu/v4l2`: `frkoenig@chromium.org` or `nhebert@chromium.org`.

Google already chose the shape of this in July 2026. Bug 530450488 (author
amazingfate) lets one build contain both VA-API and V4L2. The feature
`PreferV4L2VideoAcceleration` picks V4L2 at run time and defaults off. It
switches the whole pipeline.

The run line for a distro build that already passes `use_v4l2_codec=true` is:

```
--enable-features=PreferV4L2VideoAcceleration,AcceleratedVideoDecoder
```

Both features exist. `PreferV4L2VideoAcceleration` defaults off.
`AcceleratedVideoDecoder` defaults on only when VA-API is compiled. Leave that
default upstream. A V4L2-only build does not turn the decoder on by itself.

## The sandbox

On desktop Linux, main's `V4L2Device` looks for decoders at `/dev/videoN` and
`/dev/mediaN`. It pairs a decoder with its media controller by `bus_info`, and
by driver name when `bus_info` is empty. The GPU process broker policy allows
V4L2 nodes only on ChromeOS and Chromecast, and only under the ChromeOS names
`/dev/video-decN`, `/dev/media-decN` and `/dev/video-encN`. Reading the policy,
every open of a desktop decoder node would be denied once the GPU sandbox is
engaged.

On the only machine tested (Apple M2 Max, Asahi Mesa, 19 November 2026) the GPU
seccomp sandbox does not engage with default flags. Stock Arch Linux ARM
Chromium 157, run with every sandbox on, logs `InitializeSandbox() called with
multiple threads in process gpu-process`, its GPU process runs with
`Seccomp: 0`, and it opens `/dev/video0` and `/dev/media0`. With
`--gpu-sandbox-start-early` the sandbox engages (`Seccomp: 2`), and then the
GPU process cannot load Mesa (`Could not dlopen native EGL: libEGL.so.1:
Permission denied`) and exits. That is a separate gap (the pre-sandbox hook
preloads GL only for the GPU vendors it knows) and not part of this proposal.

So B1 is about correctness wherever the sandbox does engage. It is not a fix
for something Apple silicon users hit today.

An earlier patch set of ours (Chromium 148) made Linux look only under the
ChromeOS names and relied on a udev rule to create them. Without the links,
the decoder logged `No V4L2 API found for profile: h264 high` and a WebRTC
H.264 receiver got `NullVideoDecoder` and no picture. Main does not do that,
and that patch is not proposed.

## What the change would do

1. Keep `use_v4l2_codec` off for official Chrome. Distros that want the
   decoder already pass it (Raspberry Pi OS, Rockchip boards, Arch Linux ARM).

2. Let the GPU sandbox allow the decoder nodes that exist (B1). Only when
   accelerated decode is on and V4L2 is the active Linux decoder
   (`ActiveLinuxVideoDecoderType()`), before the sandbox starts,
   `FindV4L2DecoderDevicePaths()` opens each `/dev/videoN` and keeps it only if
   it is memory-to-memory, takes a compressed video format that is not JPEG,
   and produces no compressed format. For each decoder it also keeps the
   `/dev/mediaN` that `V4L2Device` pairs with it. Only those paths are
   allowed. Cameras, capture cards and v4l2loopback devices are not
   memory-to-memory; encoders, JPEG codecs and image processors are not
   decoders. The ChromeOS names and encoder nodes are not added on desktop,
   because `V4L2Device` does not open them there.

   Open questions for the sandbox owners, stated in B1's description:
   - The existing ChromeOS rule avoids a `FileEnumerator` on purpose. B1's
     list is fixed when the GPU process starts, so a decoder that appears
     later is not allowed until the GPU process restarts, and nodes are
     allowed by number, so an unbound decoder's number could be reused by
     another device until then.
   - The scan opens every `/dev/videoN`, cameras included. Opening a camera
     node can wake a USB camera from autosuspend or power its sensor. It runs
     only when V4L2 decoding will be used.

3. Leave the V4L2 encoder ChromeOS-only until an owner asks for it. On main,
   `media/gpu/v4l2/BUILD.gn` adds `v4l2_video_encode_accelerator.cc` only
   inside `if (is_chromeos)`.

4. Who it helps. The stateless decode fixes (A2 to A6) help drivers whose
   stateless decoder is slice-based or needs HEVC slice parameters: Apple's
   AVD on Asahi, and cedrus. In kernel 7.2 Hantro, rkvdec, MediaTek and Tegra
   decode H.264 frame-based only, so their H.264 path is unchanged; rkvdec and
   cedrus now also receive HEVC slice parameters. Only AVD was tested.
   Raspberry Pi OS uses the stateful decoder (`bcm2835-codec`), which these
   fixes do not touch. The sandbox change matters wherever the GPU sandbox
   engages.

## What stays out

- Do not default `AcceleratedVideoDecoder` on for a V4L2-only build upstream.
- Do not spread encoder sessions across encoder nodes inside Chromium. A cap
  of two sessions per Apple AVE node is a driver fact, not a generic fix.

## Software fallback

When the V4L2 decoder is missing or fails, a call must still show video,
decoded in software. Tested on the same machine with the previous round's
build of main with these changes (WebRTC loopback, OpenH264 sender, 1280x720):

- Decoder present at browser start but failing when the call starts: the call
  decodes in software (FFmpeg), 270 frames, 0 dropped, including H.264 High.
- No hardware decoder from the start: the receiver does not offer H.264 High.
  A one-codec test then shows no video; a real call would agree on another
  profile or codec. Stock Chromium behaves the same.
