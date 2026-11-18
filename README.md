# 🎨 Omarchy Chromium

[![AUR version](https://img.shields.io/aur/version/omarchy-chromium-bin)](https://aur.archlinux.org/packages/omarchy-chromium-bin)
[![GitHub release](https://img.shields.io/github/v/release/omacom-io/omarchy-chromium)](https://github.com/omacom-io/omarchy-chromium/releases)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue)](LICENSE)

A custom build of Chromium with the **Omarchy theme patches** - providing command-line theme switching capabilities for seamless integration with your desktop environment.

## Apple Silicon V4L2 (branch `smartroom/v4l2-direct`)

This branch builds Chromium 148.0.7778.96 for aarch64 so decode and encode both go through Chromium's V4L2 code. `chromium.args.arm64.gn` sets `use_v4l2_codec=true` and `use_vaapi=false`. The x86_64 `PKGBUILD` is unchanged. `PKGBUILD.arm64` does not depend on libva, so the package does not require `libva-v4l2-request`. HEVC stays available because `proprietary_codecs` already turns on `enable_hevc_parser_and_hw_decoder` for `is_linux`.

Apple AVD is a stateless request-API decoder. Its video node name is `avd`, and it exposes H.264 as `V4L2_PIX_FMT_H264_SLICE`, HEVC as `V4L2_PIX_FMT_HEVC_SLICE`, and VP9 as `V4L2_PIX_FMT_VP9_FRAME`, with `NV12` capture and `P010` for 10-bit. Aurora's AVE encoder is stateful mem2mem. Its video node name is `apple-ave`, it takes `NV12`, and it produces stateful H.264 and HEVC. ChromeOS opens `/dev/video-decN`, `/dev/media-decN`, and `/dev/video-encN`. Those are also the only V4L2 paths the GPU sandbox broker allows. Desktop Linux otherwise scans `/dev/videoN`, and on desktop Linux the broker never grants a V4L2 node. The patches and the udev rule below are the small change that makes Chromium find AVD and AVE. `SMARTROOM.md` has the build and test notes.

| File | Why it is here |
| --- | --- |
| `011-linux-v4l2-device-names.patch` | Desktop Linux looks up the ChromeOS device names and still applies the Linux pixel-format filter, so a camera symlinked onto those names is rejected. The scan is ten nodes, which matches the broker (`video-dec0..4`, `video-enc0..4`). The request-API media controller is `/dev/media-decN`. |
| `012-linux-v4l2-gpu-sandbox.patch` | When the binary is built with V4L2, the desktop Linux GPU broker allows those ChromeOS names and then still allows the DRM render nodes. `UseV4L2Codec()` is false when `USE_V4L2_CODEC` is unset, so a VA-API x86_64 build does not gain these paths. |
| `013-v4l2-decode-feature-default.patch` | `AcceleratedVideoDecoder` defaults on when VA-API or V4L2 is compiled in. Encode stays off until `AcceleratedVideoEncoder` is passed, which the Omarchy kiosk already passes. |
| `004-linux-v4l2-encode-keep-vaapi.patch` | Builds `v4l2_video_encode_accelerator.cc` on Linux and registers that encoder. With `use_vaapi=false`, the existing decoder `#elif USE_V4L2_CODEC` selects `V4L2VideoDecoder`. AVD's slice and frame fourccs make `IsV4L2DecoderStateful()` return false, so the stateless backend is used. |
| `chromium-v4l2.rules` | Symlinks the `avd` video node to `/dev/video-dec0` and the `avd` media node to `/dev/media-dec0`. The two M2 `apple-ave` nodes are pinned to `/dev/video-enc0` and `/dev/video-enc1` by platform address. The rules match `add` and `change`, because a later change event drops a symlink whose rule matched only `add`. Other SoCs need their own matches. |
| `chromium-v4l2.install` | Reloads udev and sends an `add` trigger on install, upgrade, and removal so the symlinks appear without a reboot. |

## ✨ Features

- 🎨 **Dynamic Theme Switching** - Change Chromium's theme via command-line flags
- 🚀 **Built from Source** - Using Google's official Chromium source with bundled toolchain
- 📦 **AUR Package** - Easy installation for Arch Linux users
- 🔄 **Automated Updates** - Scripts to track upstream Chromium releases
- 🛠️ **Developer Friendly** - Full build automation and release pipeline

## 📥 Installation

### Option 1: Install from AUR (Recommended)

The package is available in the AUR: https://aur.archlinux.org/packages/omarchy-chromium-bin

```bash
# Using an AUR helper (if you have one installed)
yay -S omarchy-chromium-bin
# OR
paru -S omarchy-chromium-bin

# Manual installation (without AUR helper)
git clone https://aur.archlinux.org/omarchy-chromium-bin.git
cd omarchy-chromium-bin
makepkg -si
```

### Option 2: Download Pre-built Binary
Download the latest `.pkg.tar.zst` from [Releases](https://github.com/omacom-io/omarchy-chromium/releases) and install:
```bash
sudo pacman -U omarchy-chromium-*.pkg.tar.zst
```

### Option 3: Build from Source
```bash
git clone https://github.com/omacom-io/omarchy-chromium.git
cd omarchy-chromium
makepkg -si
```

## 🎨 Theme Usage

**GM3-compliant theme switches** - change themes without opening new windows:

```bash
# Set custom user color (RGB values)
chromium --no-startup-window --set-user-color="28,32,39"

# Switch color scheme
chromium --no-startup-window --set-color-scheme="dark"
chromium --no-startup-window --set-color-scheme="light"

# Set color variant
chromium --no-startup-window --set-color-variant="vibrant"

# Enable grayscale theme
chromium --no-startup-window --set-grayscale-theme="true"

# Reset to default theme
chromium --no-startup-window --set-default-theme
```

> **Note**: These are Material Design 3 (GM3) compliant switches. The `--no-startup-window` flag applies changes to existing windows without opening a new one.

## 🏗️ Project Structure

The project consists of three main components:

| Directory | Purpose |
|-----------|---------|
| `~/omarchy-chromium` | **Build repository** - Contains PKGBUILD, patches, and automation scripts |
| `~/omarchy-chromium-src` | **Chromium source** - Official Chromium checkout with Omarchy patches applied (not committed) |
| `~/BUILD_LAB/omarchy-chromium-bin` | **AUR package** - Binary package metadata for AUR distribution |

## 🔧 Development

### Initial Setup

> besides AUR everything is meant to be done/initialized by `makepkg -s` itself

1. **Setup AUR package repository:**
   ```bash
   mkdir -p ~/BUILD_LAB
   git clone ssh://aur@aur.archlinux.org/omarchy-chromium-bin.git ~/BUILD_LAB/omarchy-chromium-bin
   
   ```

2. **Configure GitHub CLI (for releases):**
   ```bash
   gh auth login
   # Follow prompts to authenticate with GitHub
   ```

## 📜 Automation Scripts

### 🎯 `smart_update.sh` - Upstream-Aware Updates (Recommended)

**Only builds and pushes to AUR when upstream Chromium has changes!**

This is the **recommended way** to keep your package updated - it ensures you only push to AUR when there's an actual new Chromium release from Arch Linux.

#### Usage:
```bash
# Check upstream and update if needed
./smart_update.sh
```

#### What it does:
- ✅ Checks if Arch Linux has released a new Chromium version
- ✅ Only proceeds if there are upstream changes
- ✅ Automatically runs update_to_upstream.sh and do_update.sh
- ✅ Prevents unnecessary AUR updates
- ✅ Saves build time and resources

---

### 🔍 `check_upstream.sh` - Check for Updates

Checks if the upstream Arch Linux Chromium package has a newer version than ours.

#### Usage:
```bash
# Check if updates are available
./check_upstream.sh
```

#### Returns:
- Exit code 0: Update available
- Exit code 1: Already up-to-date
- Exit code 2: Error occurred

---

### 🚀 `do_update.sh` - Manual Build & Release

Use this for hotfixes, patches, or when you need to force a release regardless of upstream status.

1. **Increments** `pkgrel` by one
2. **Builds** package using `makepkg -s`
3. **Uploads** to GitHub Releases
4. **Updates** AUR package metadata

#### Usage:
```bash
# Full build and release (for patches/fixes)
./do_update.sh

# Skip build (use existing package)
SKIP_BUILD=1 ./do_update.sh
```

#### When to use:
- When you've made patches or fixes
- For emergency updates
- When smart_update.sh says no update but you need to release

---

### 🔄 `update_to_upstream.sh` - Sync with Upstream

Synchronizes with the latest official Chromium release:

1. **Fetches** latest version from Arch Linux's Chromium package
2. **Updates** local PKGBUILD version
3. **Stashes** local changes in Chromium checkout
4. **Checks out** new Chromium version tag
5. **Applies** Omarchy theme patches
6. **Prepares** build environment

#### Usage:
```bash
# Manually sync to latest upstream
./update_to_upstream.sh

# Then build
makepkg -s
```

#### What it does:
- ✅ Automatically detects new Chromium versions
- ✅ Preserves your local modifications
- ✅ Applies compatible patches only
- ✅ Ready to build immediately

## 🔄 Typical Workflow

### Recommended: Smart Update (checks upstream first)
```bash
cd ~/omarchy-chromium
./smart_update.sh  # Only builds if Arch has new Chromium
```

### Manual Update for Patches/Fixes
```bash
cd ~/omarchy-chromium
./do_update.sh  # Increments pkgrel, builds, releases
```

### Update to New Chromium Version (manual)
```bash
cd ~/omarchy-chromium
./update_to_upstream.sh  # Updates to latest Chromium
./do_update.sh          # Builds and releases
```

### Quick Re-release (no rebuild)
```bash
cd ~/omarchy-chromium
SKIP_BUILD=1 ./do_update.sh  # Uses existing package
```

### Check if updates are available
```bash
cd ~/omarchy-chromium
./check_upstream.sh  # Shows if Arch has newer version
```

## 🤖 GitHub Actions Automation

Automated builds using self-hosted GitHub runners with multiple workflow types.

📋 **[Complete GitHub Workflows Documentation →](GITHUB_WORKFLOWS.md)**

**Quick Overview:**
- 🌙 **Nightly Builds**: Daily automated builds (01:00 UTC)  
- 🔨 **Manual Full Build**: Complete rebuilds from source
- 🎨 **Test Theme Patch**: Isolated patch testing
- ⚡ **Quick Release**: Fast AUR release testing

[View all workflows →](GITHUB_WORKFLOWS.md)

## 🛠️ Build Configuration

The build uses Google's bundled toolchain for maximum compatibility:

- **Clang/LLVM**: Version 21 (bundled)
- **Rust**: Bundled toolchain
- **PGO**: Profile-Guided Optimization enabled
- **CFI**: Control Flow Integrity enabled
- **Patches Applied**:
  - ✅ `omarchy-theme-switcher.patch` - Core theme functionality
  - ✅ `use-oauth2-client-switches-as-default.patch` - OAuth2 support
  - ❌ `compiler-rt-adjust-paths.patch` - Skipped (bundled toolchain)
  - ❌ `chromium-*-nodejs-version-check.patch` - Skipped (bundled Node.js)
  - ❌ `increase-fortify-level.patch` - Skipped (conflicts with bundled build)

## 📊 Build Requirements

- **Disk Space**: ~100GB (source + build artifacts)
- **RAM**: 16GB minimum, 32GB recommended
- **Build Time**: 3-4 hours on modern hardware
- **Network**: Fast connection for initial checkout (~30GB)

## 🔧 Patch Maintenance

### Theme Switcher Patch (IMPORTANT)

The core `omarchy-theme-switcher.patch` is based on an upstream Chromium change request:

**📎 Upstream CL**: [https://chromium-review.googlesource.com/c/chromium/src/+/6832165](https://chromium-review.googlesource.com/c/chromium/src/+/6832165)

#### If the patch fails to apply:

1. **Visit the CL** and check its merge status
2. **Fix merge conflicts** in the CL to keep it mergeable with main
3. **Download the updated diff**:
   ```bash
   # From the CL page, click "Download" and select "Patch"
   # Or use git:
   cd ~/omarchy-chromium-src/src
   git fetch https://chromium.googlesource.com/chromium/src refs/changes/65/6832165/[LATEST_PATCHSET]
   git format-patch -1 FETCH_HEAD -o ~/omarchy-chromium/
   ```
4. **Replace** `omarchy-theme-switcher.patch` with the new version
5. **Test** the build with the updated patch

> **Note**: Keeping the CL mergeable with Chromium main branch is crucial for maintaining this project. If you encounter merge conflicts, please help by updating the CL!


## 🧪 Testing

Comprehensive testing procedures for theme functionality and build system.

📋 **[Complete Testing Documentation →](TESTING.md)**

**Quick Testing:**
```bash
# Run theme command line handler tests
cd ~/omarchy-chromium-src/src
tools/autotest.py -C out/Release --gtest_repeat=1 chrome/browser/themes/theme_command_line_handler_unittest.cc
```

[View all testing procedures →](TESTING.md)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly (including unit tests above)
4. Submit a pull request

### Testing Patches
```bash
cd ~/omarchy-chromium-src/src
# Apply your patch
patch -p1 < ~/your-patch.patch
# Test build
autoninja -C out/Release chrome
# Run theme tests
tools/autotest.py -C out/Release --gtest_repeat=1 chrome/browser/themes/theme_command_line_handler_unittest.cc
```

## 📝 License

This project is licensed under the BSD-3-Clause License - same as Chromium.

## 🙏 Credits

- **Chromium Project** - The amazing open-source browser
- **Arch Linux** - Package maintainers and build infrastructure
- **Omarchy** - Theme integration concept
- **Contributors** - Everyone who has helped improve this project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/omacom-io/omarchy-chromium/issues)
- **AUR Comments**: [AUR Package Page](https://aur.archlinux.org/packages/omarchy-chromium-bin)
- **Maintainer**: Helmut Januschka <helmut@januschka.com>

---

<div align="center">
Made with ❤️ for the Arch Linux community
</div>
