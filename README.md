# V4L2 stateless decode fixes for Chromium main

These are patches for Chromium, prepared for code review. Nothing here has been
uploaded to Gerrit. Lucas Goossen uploads them himself, after an independent
review and after the contributor agreement is on file.

They make Chromium's V4L2 stateless decoder work on drivers that decode one
slice per request, such as Apple's AVD on the M2 Max, without changing the
frame-based path that ChromeOS devices use today. The last patch lets a
desktop Linux build with `use_v4l2_codec=true` reach its V4L2 codec nodes
wherever the GPU sandbox engages.

Base: Chromium main `98478f51939a` (18 November 2026). Apply with
`git am patches/*.patch` in a checkout of that commit.

| Patch | Change | Description file |
|---|---|---|
| 0001 | Expect the linear modifier in layout tests on Linux (test only) | `CL-A0-layout-test-modifier.md` |
| 0002 | Give single-buffer P010 a second color plane | `CL-A1-p010-plane.md` |
| 0003 | Size the stateless coded format before probing it | `CL-A2-coded-size-probe.md` |
| 0004 | Support slice-based stateless H.264 decoders | `CL-A3-h264-slice-based.md` |
| 0005 | Submit only reference pictures in a slice-based H.264 DPB | `CL-A4-h264-reference-dpb.md` |
| 0006 | Decode multi-slice H.264 pictures on slice-based devices | `CL-A5-h264-multi-slice.md` |
| 0007 | Send HEVC slice parameters to stateless decoders | `CL-A6-hevc-slice-params.md` |
| 0008 | Allow V4L2 codec nodes in the desktop Linux GPU sandbox | `CL-B1-sandbox-codec-nodes.md` |

0001 fixes three existing unit tests that fail in a Linux build; 0002 extends
the same test file, so send 0001 first. 0002 to 0007 are the decode fixes.
0005 needs 0004, and 0006 needs 0005. The others stand alone. 0008 does not
depend on them. It belongs with the desktop-V4L2 proposal in
`CL-B-desktop-v4l2.md`, not with the decode fixes. 0008 applies to bare main.
The same change on top of 0001-0007 is `patches/on-a/0008-...patch` (only
the `BUILD.gn` context differs).

Each description file holds the Gerrit description, the files, the reviewers,
the unit tests and the hardware results.

`tests/` holds the Studio test scripts. `sr-play.py` plays clips and reports
the decoder, frames, drops and CPU. `sr-webrtc.sh` runs a WebRTC loopback
call, and can hide the hardware decoder to test the software fallback. Both
start Chrome with every sandbox on and a throwaway profile.

`tools/mkcl.py` regenerates the description files from the commit messages.
`tools/remsg.py` rewrites commit messages without touching a working tree.

The test build used `use_v4l2_codec=true`, `use_vaapi=false`,
`proprietary_codecs=true` and `ffmpeg_branding="Chrome"`, with system clang
23.1.3 and rustc 1.99.0 on aarch64. The rest of the build setup is
described in `REPORT.md` of the job directory. It is local build plumbing, not
part of these patches.
