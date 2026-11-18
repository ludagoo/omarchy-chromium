# SmartRoom Chromium, direct V4L2

Branch `smartroom/v4l2-direct` of [ludagoo/omarchy-chromium](https://github.com/ludagoo/omarchy-chromium), cut from `smartroom/v4l2` at `8d21064`. That parent is Chromium 148.0.7778.96 with VA-API decode kept and a V4L2 stateful encoder added. This branch turns VA-API off on arm64 and uses Chromium's own V4L2 decoder and encoder.

Package: `omarchy-chromium-smartroom-v4l2-direct` 148.0.7778.96-24. `pkgrel=24` sorts above Omarchy's `omarchy-chromium-bin` 148.0.7778.96-22 and above the previous test package `-23`. It `provides` `chromium` and `omarchy-chromium`, and `conflicts` / `replaces` `omarchy-chromium-bin`.

The x86_64 `PKGBUILD` is not modified. New patches are inert there: `use_v4l2_codec` stays false, `UseV4L2Codec()` returns false, and `AcceleratedVideoDecoder` stays on because `use_vaapi` is true.

## GN args

`chromium.args.arm64.gn` is what the gclient path copies to `out/aarch64/args.gn`. The tarball path (`_use_chromium_src=0`) does not read that file, so `PKGBUILD.arm64` `build()` appends the same args.

| Arg | Value | Why |
| --- | --- | --- |
| `use_v4l2_codec` | `true` | `media/gpu/args.gni` defaults this to false. Turns on `//media/gpu/v4l2`. |
| `use_vaapi` | `false` | Default is true on Linux arm64 when Ozone X11 or Wayland is on. Set false so `video_decoder_pipeline.cc` takes the `#elif USE_V4L2_CODEC` arm. `use_linux_video_acceleration` is `use_vaapi \|\| use_v4l2_codec`, so the linux video stack stays on. |
| `use_remoteexec` / `use_siso` | `false` | Omarchy's RBE is not on this build machine. Official release tarball, system clang, local ninja. |
| `use_thin_lto` | `false` | ThinLTO links do not fit comfortably in 31 GB. |
| `is_cfi` | `false` | CFI requires ThinLTO (`assert(!is_cfi \|\| use_thin_lto)`). |
| `chrome_pgo_phase` | `0` | Skips the official PGO profile. |
| `concurrent_links` | `1` | One link at a time. |
| `target_cpu` / `target_os` | `arm64` / `linux` | Native Studio build. |

`proprietary_codecs=true` leaves `enable_hevc_parser_and_hw_decoder` on for `is_linux` (`media/media_options.gni`). HEVC does not need an extra flag. `use_v4lplugin` stays false. That flag is the libv4l2 conversion plugin, not the kernel mem2mem device.

The arm64 package does not depend on libva. ffmpeg on the Studio may still pull libva in for other packages. This package does not depend on `libva-v4l2-request` (the installed shim is `libva-v4l2_request-avd`).

## Patches

`004-linux-v4l2-encode-keep-vaapi.patch` (from the parent branch) drops the mutual-exclusion asserts, builds `v4l2_video_encode_accelerator.cc` when `is_linux`, and makes `CreateV4L2VEA()` return a real encoder on Linux when `AcceleratedVideoEncoder` is enabled. The factory tries V4L2 first. With `use_vaapi=false` the asserts would have passed anyway. The encoder source list and the Linux `CreateV4L2VEA()` are why the patch stays. The decoder `#if` is left as upstream wrote it. VA-API off is what selects V4L2 decode.

`007-v4l2-vaapi-image-processor.patch` and `008-fourcc-vaapi-and-v4l2.patch` existed so a both-flags build could compile. This branch compiles V4L2 only, and those two patches are not in the tree.

`011-linux-v4l2-device-names.patch` points the non-ChromeOS enumerator at `/dev/video-decN`, `/dev/video-encN`, `/dev/image-procN`, `/dev/jpeg-decN`, and `/dev/jpeg-encN`, and points `GetRequestsQueue()` at `/dev/media-decN`. The scan is 10 nodes. ChromeOS still opens the legacy unnumbered node. The Linux pixel-format filter is unchanged: a decoder or encoder is accepted when every input format is a non-JPEG coded format (including `H264_SLICE`, `HEVC_SLICE`, and `VP9_FRAME`) and some output format is a raw pixel fourcc. A camera does not pass that test.

`012-linux-v4l2-gpu-sandbox.patch` calls `AddV4L2GpuPermissions()` from the desktop Linux fall-through of `FilePermissionsForGpu()` when `UseV4L2Codec()` is true, then still calls `AddStandardGpuPermissions()` for the DRM nodes. The helper allows `/dev/video-dec0..4`, `/dev/media-dec0..4`, `/dev/video-enc`, and `/dev/video-enc0..4`. It does not allow `/dev/videoN`. Out-of-process video decode is ChromeOS-only, so the GPU process is the one that opens these nodes. The kiosk's GPU feature status is already "Hardware accelerated" for decode, which sets `accelerated_video_decode_enabled` on the sandbox options.

`013-v4l2-decode-feature-default.patch` defaults `kAcceleratedVideoDecodeLinux` (`AcceleratedVideoDecoder`) on when `USE_VAAPI` or `USE_V4L2_CODEC` is set. `AcceleratedVideoEncoder` stays off unless the caller enables it.

`014-tsbuildinfo-before-tsc.patch` deletes `tsconfig_*.tsbuildinfo` before `tsc` runs. A killed compiler leaves that file, and the next `tsc` then exits 0 without writing outputs. GN marks the action done, and a later target fails with `TS2307` because `tsc/` is empty. The Studio reboots during this build, which is how it showed up.

Compile fixes kept from the parent branch: `005-unbundle-libpng-testonly.patch`, `006-rust-1.99-bytemuck.patch`, `009-glibc-2.43-sys-seccomp.patch`, `010-rust-1.99-qr-code.patch`, `glibc-2.42-baud-rate-fix.patch`, plus the Omarchy theme patches, Widevine, oauth, fortify, and the nodejs check. `compiler-rt-adjust-paths.patch` is skipped. It does not apply on Clang 23.

## udev

`chromium-v4l2.rules` installs as `/usr/lib/udev/rules.d/70-chromium-v4l2.rules`.

| Match | Symlink |
| --- | --- |
| `SUBSYSTEM=="video4linux"`, `ATTR{name}=="avd"` | `/dev/video-dec0` |
| `SUBSYSTEM=="media"`, `ATTR{model}=="avd"` | `/dev/media-dec0` |
| `SUBSYSTEM=="video4linux"`, `ATTR{name}=="apple-ave"` | `/dev/video-encN` for the first free N in 0..4 |

The encoder index comes from `/usr/lib/chromium/chromium-v4l2-enc-index`. It takes `flock` on `/run/lock/chromium-v4l2-enc.lock` and prints one integer. udev turns that into `%c`. Two AVE nodes (the M2 has `40d100000.video-codec` and `507100000.video-codec`) get `video-enc0` and `video-enc1`. A node past index 4 would be invisible to the broker, so the helper exits 1 and udev skips the symlink.

The symlinks do not change the target mode. The nodes are `root:video` mode `0660` with the seat `uaccess` ACL. The rules add `TAG+="uaccess"` as well. The kiosk user is in group `video`. v4l2loopback cameras are not matched: their sysfs name is not `avd` or `apple-ave`.

`chromium-v4l2.install` reloads udev and runs `udevadm trigger --action=add` for `video4linux` and `media` on install, upgrade, and removal. The rules match `ACTION=="add"`. A trigger without `--action=add` sends `change` and does not create the symlinks. Checked on the Studio: after `--action=add`, `/dev/video-dec0` points at `video0` and `/dev/media-dec0` points at `media0`.

Checked on the Studio before the build: `/dev/video0` is `ATTR{name}=="avd"` at `287080000.avd`, and `/dev/media0` is `ATTR{model}=="avd"`. AVE is not bound on this firmware. The expected runtime result is an empty encoder list and a browser that still plays and joins a meeting.

AVD's media controller `bus_info` is `platform:avd` and the driver name is `avd`, matching the video node, so `GetRequestsQueue()` pairs them.

## Runtime flags

The Room Controller already passes `AcceleratedVideoEncoder`. It does not pass `AcceleratedVideoDecoder`. Patch 013 makes that default on for this binary, so the kiosk flags stay as they are. `VaapiVideoDecoder` and `VaapiVideoEncoder` in the kiosk flag list are unused names in this build. They do not select the VA-API classes, which are not compiled.

## Build

Native on the Studio, as the `srbuild` user, from this tree:

```
MAKEFLAGS=-j$(($(nproc)-2)) makepkg -s --noconfirm -p PKGBUILD.arm64
```

`build()` runs ninja at `nproc-2` and keeps `concurrent_links=1`. Resume a partial tree with `makepkg --noextract`.

Chromium 148 renamed the unbundle library from `harfbuzz-ng` to `harfbuzz`. `PKGBUILD.arm64` uses that key. System Rust comes from rustup (`rustc` 1.99 for this build). `rust_sysroot_absolute` is `rustc --print sysroot`, and `rustc_version` is only the numeric version. `PKGBUILD.arm64` strips makepkg's `-march=armv8-a` so libyuv's `+dotprod+i8mm` march survives. The lite tarball's esbuild, gperf, and Rollup native binding are x86-64. `prepare()` installs the linux-arm64 esbuild and `@rollup/rollup-linux-arm64-gnu`, and points gperf at `/usr/bin/gperf`.

## Install

Keep the stock package file so it can be installed again:

```
sudo pacman -U omarchy-chromium-smartroom-v4l2-direct-148.0.7778.96-24-aarch64.pkg.tar.zst
```

The Room Controller relaunches Chromium. Then:

1. `/dev/video-dec0` and `/dev/media-dec0` exist and point at the AVD nodes.
2. `chrome://gpu` Video Acceleration lists V4L2 decoders for H.264, VP9 profile 0, VP9 profile 2, and HEVC. The encoder list stays empty while AVE is unbound.
3. `chrome://media-internals` names a V4L2 decoder, dropped frames stay at zero, and CPU stays in the same range as the stock `VaapiVideoDecoder` path for 1080p and 4K.
4. One Zoom test meeting still connects. Encode of the meeting stays on OpenH264 until an `apple-ave` node exists.

Roll back with the saved `omarchy-chromium-bin` package if decode falls back to software, frames drop, or the meeting breaks.
