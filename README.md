# V4L2 stateless decode fixes for Chromium main

These are patches for Chromium, prepared for code review. Nothing here has been
uploaded to Gerrit. Lucas Goossen uploads them himself, after an independent
review and after the contributor agreement is on file.

They make Chromium's V4L2 stateless decoder work on drivers that decode one
slice per request, such as Apple's AVD on the M2 Max, without changing the
frame-based path that ChromeOS devices use today. The last patch lets a
desktop Linux build with `use_v4l2_codec=true` reach its V4L2 codec nodes with
the GPU sandbox on.

Base: Chromium main `98478f51939a` (18 November 2026). Apply with
`git am patches/*.patch` in a checkout of that commit.

| Patch | Change | Description file |
|---|---|---|
| 0001 | Give single-buffer P010 a second color plane | `CL-A1-p010-plane.md` |
| 0002 | Size the stateless coded format before probing it | `CL-A2-coded-size-probe.md` |
| 0003 | Support slice-based stateless H.264 decoders | `CL-A3-h264-slice-based.md` |
| 0004 | Submit only reference pictures in a slice-based H.264 DPB | `CL-A4-h264-reference-dpb.md` |
| 0005 | Decode multi-slice H.264 pictures on slice-based devices | `CL-A5-h264-multi-slice.md` |
| 0006 | Send HEVC slice parameters to stateless decoders | `CL-A6-hevc-slice-params.md` |
| 0007 | Allow V4L2 codec nodes in the desktop Linux GPU sandbox | `CL-B1-sandbox-codec-nodes.md` |

0001 to 0006 are the decode fixes. 0004 needs 0003, and 0005 needs 0004. The
others stand alone. 0007 does not depend on them. It belongs with the
desktop-V4L2 proposal in `CL-B-desktop-v4l2.md`, not with the decode fixes.

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
