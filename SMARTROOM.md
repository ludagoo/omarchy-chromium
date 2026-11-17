# SmartRoom Chromium V4L2 test build

Branch `smartroom/v4l2` of [ludagoo/omarchy-chromium](https://github.com/ludagoo/omarchy-chromium), cut from commit `8ca4ea9515c2aa329898c2f21566748ff92d0881`. That commit is what GitHub tag `v148.0.7778.96-21` points at. Omarchy's binary package `omarchy-chromium-bin` 148.0.7778.96-22 on `pkgs.omarchy.org` stable/aarch64 wraps that same GitHub release (`_build=21`). The packaging repo's committed `pkgver` was still 145.0.7632.75; this branch sets `pkgver=148.0.7778.96` so the tree matches the browser Omarchy ships.

Package: `omarchy-chromium-smartroom-v4l2` 148.0.7778.96-23. `pkgrel=23` sorts above Omarchy's 22. It `provides` `chromium` and `omarchy-chromium`, and `conflicts` / `replaces` `omarchy-chromium-bin`.

Do not install this into a Studio image. It is a test package only.

## GN args

`chromium.args.arm64.gn` is what the gclient path copies to `out/aarch64/args.gn`. The tarball path (`_use_chromium_src=0` in `PKGBUILD.arm64`) does not read that file, so the same args are also appended in `build()`.

| Arg | Value | Why |
| --- | --- | --- |
| `use_v4l2_codec` | `true` | `media/gpu/args.gni` defaults this to false. Turns on `//media/gpu/v4l2`, including the stateless decoder (`v4l2_video_decoder_backend_stateless.cc`) and, with the patch below, the stateful encoder. |
| `use_vaapi` | `true` | Default on Linux arm64 when Ozone X11 or Wayland is on (`build/config/ozone.gni` enables both for `is_linux`). Set explicitly so VA-API cannot be dropped. `use_linux_video_acceleration` is `use_vaapi \|\| use_v4l2_codec`. |
| `use_remoteexec` / `use_siso` | `false` | Omarchy's RBE is not on the studio build VM. Official release tarball, system clang, local ninja. |
| `use_thin_lto` | `false` | `build/config/compiler/compiler.gni` turns ThinLTO on for official Clang builds. Linking that on 16 GB RAM fails. |
| `is_cfi` | `false` | CFI requires ThinLTO (`assert(!is_cfi \|\| use_thin_lto)`). |
| `chrome_pgo_phase` | `0` | Skips the official PGO profile. The arm64 profile is optional for a functional test build. |
| `concurrent_links` | `1` | One link at a time on 16 GB. |
| `target_cpu` / `target_os` | `arm64` / `linux` | Native Studio build. |

`use_v4lplugin` stays false. That flag is the libv4l2 conversion plugin, not the kernel mem2mem device.

## Why a patch

Chromium 148.0.7778.96 will not compile VA-API and V4L2 together:

- `media/gpu/BUILD.gn` and `media/gpu/chromeos/BUILD.gn` have `assert(!(use_v4l2_codec && use_vaapi))`.
- `media/gpu/v4l2/BUILD.gn` compiles `v4l2_video_encode_accelerator.cc` only when `is_chromeos`.
- `CreateV4L2VEA()` in `gpu_video_encode_accelerator_factory.cc` returns nullptr unless `IS_CHROMEOS`. The comment points at crbug.com/901264 (DMA-buf offsets passed via `data_offset`, which is not in the V4L2 spec).

`004-linux-v4l2-encode-keep-vaapi.patch` removes the mutual-exclusion asserts, builds the stateful encoder on Linux, and registers it ahead of VA-API. On Linux the V4L2 encoder is created only when `AcceleratedVideoEncoder` is enabled, the same gate VA-API encode already uses. `GetSupportedProfiles()` is empty when no mem2mem encoder node exists, and the factory tries VA-API next.

The decoder pipeline is `#if USE_VAAPI` / `#elif USE_V4L2_CODEC`. With both flags set it stays on VA-API, so the libva-v4l2-request path is unchanged. The V4L2 stateless decoder is compiled and not selected. Do not reorder that `#if` or VA-API decode goes away.

## Runtime flags for the Room Controller

Feature names are from `media/base/media_switches.cc` at 148.0.7778.96. The 3-argument `BASE_FEATURE` form uses the explicit string. The 2-argument form drops the leading `k` (`base/feature_internal.h`).

```
chromium \
  --ozone-platform=wayland \
  --enable-features=AcceleratedVideoDecoder,AcceleratedVideoEncoder \
  --ignore-gpu-blocklist
```

- `AcceleratedVideoDecoder` (`kAcceleratedVideoDecodeLinux`) is **on by default when `USE_VAAPI` is set**, off otherwise. Pass it anyway so a field trial cannot disable decode.
- `AcceleratedVideoEncoder` (`kAcceleratedVideoEncodeLinux`) is **off by default** on Linux. Without it both `CreateV4L2VEA()` and `CreateVaapiVEA()` return nullptr and encode is software.
- `AcceleratedVideoDecodeLinuxGL` is on by default (2-argument feature, name keeps the identifier without `k`).
- `VaapiIgnoreDriverChecks` exists and defaults off. Nothing in `media/gpu/vaapi/vaapi_wrapper.cc` reads it. VA-API init accepts any vendor string (`kOther` is allowed). libva-v4l2-request does not need this flag unless a later check shows up in chrome://gpu.
- `--ignore-gpu-blocklist` covers the GPU process blocklist, which is separate from the VA-API feature.

Aurora's AVE driver does not list the M2 Max (t6021) yet. Encode cannot be proven on current Studios. The binary is ready for a machine whose kernel exposes a V4L2 stateful encoder.

## Build

On the Arch Linux ARM VM (`studio-build`), from this tree, with `PKGBUILD.arm64`:

```
MAKEFLAGS=-j6 PKGDEST=$HOME/fw-build/out/chromium-v4l2 makepkg -s --noconfirm -p PKGBUILD.arm64
```

The VM has no V4L2 device. A headless smoke test can only show that the binary exists and that V4L2 encode symbols were linked:

```
/usr/lib/chromium/chromium --headless=new --disable-gpu --no-sandbox --version
strings /usr/lib/chromium/chromium | grep -m1 V4L2VideoEncodeAccelerator
```

`chrome://gpu` via `--dump-dom` will not report hardware encode without a device.

## Install on a Studio

Stock package is `omarchy-chromium-bin`. Replace it with this one. Do not bake it into an image.

```
sudo pacman -U omarchy-chromium-smartroom-v4l2-148.0.7778.96-23-aarch64.pkg.tar.zst
```

Launch the kiosk with the flags above. Then:

1. `chrome://gpu` — Video Encode should say **Hardware accelerated** once the AVE node exists. Video Decode should stay hardware accelerated through VA-API / libva-v4l2-request. If decode falls back to software, compare with the stock Omarchy browser on the same machine before blaming this build. The decoder `#if` was left on VA-API.
2. `chrome://webrtc-internals` during a SmartRoom or Teams/ACS call — the outbound video codec implementation should name the V4L2 encoder (`V4L2VideoEncodeAccelerator`), not `OpenH264` or a software VP8 encoder. If the V4L2 node is missing, the factory falls through to VA-API encode and then to software. VA-API encode has no path to Aurora's AVE driver.
3. CPU — compare `chromium` CPU while encoding the room camera against the stock browser forced to software encode (`--disable-accelerated-video-encode`). Hardware encode should sit well below a full core at the kiosk's camera resolution. If CPU matches software encode, the V4L2 device is not being opened. Check `dmesg` for the AVE driver and `v4l2-ctl --list-devices` for an encoder node.

To go back:

```
sudo pacman -S omarchy-chromium-bin
```
