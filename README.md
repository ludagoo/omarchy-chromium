# chromium-smartroom 158

A Chromium 158.0.8127.36 package for the SmartRoom Mac Studio rooms. It starts
from Arch Linux ARM's `chromium` PKGBUILD and adds direct V4L2 decode and encode
on Apple's AVD and AVE. There is no VA-API and no hybrid: `use_vaapi=false`,
`use_v4l2_codec=true`.

It has been built on the Studio. It has not been installed anywhere.

What is added to Arch Linux ARM's build:

- `sr-0001` to `sr-0006`: the stateless decode fixes prepared for Chromium main
  (branch `smartroom/upstream-main`), cherry-picked onto 158 without changes.
- `sr-0007`: the GPU sandbox finds the V4L2 codec nodes itself, so Chrome needs
  no `/dev/video-dec0` links and no `--disable-gpu-sandbox`.
- `sr-0008` to `sr-0012`: room-only changes. They build the V4L2 encoder on
  desktop Linux, behind `AcceleratedVideoEncoder` like VA-API. They turn
  `AcceleratedVideoDecoder` on by default for a V4L2-only build. They spread
  encoder sessions across AVE's two nodes, add HEVC encoder controls, and feed
  CPU NV12 frames to the encoder.
- `chromium-v4l2.rules`: udev links `/dev/video-dec0`, `/dev/media-dec0`,
  `/dev/video-enc0` and `/dev/video-enc1`, kept for older kiosk scripts.
- gn 2603 from CIPD (158's own pin) replaces ALARM's gn revert patch. ALARM
  patches that 158 already contains are dropped.
- `use_thin_lto=false` and `concurrent_links=1`, because the Studio has 31 GB
  and runs a kiosk while it builds.

Build on aarch64 with `room-158-makepkg.sh prep` and then
`room-158-makepkg.sh build`, as an unprivileged user. That script uses the
rustup toolchain 1.99.0 through `SR_RUST_SYSROOT`.
