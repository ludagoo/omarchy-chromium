# V4L2 stateless decode fixes for Chromium main, second round

These are patches for Chromium, prepared for code review. Nothing here has been
uploaded to Gerrit. Lucas Goossen uploads them himself, after the contributor
agreement is on file. This round replaces `smartroom/upstream-main`. It applies
two independent reviews of that set.

The changes make Chromium's V4L2 stateless decoder work on drivers that decode
one slice per request, such as Apple's AVD on the M2 Max. Drivers that offer
frame-based H.264 decoding keep the path ChromeOS uses today.

Base: Chromium main `98478f51939a` (18 November 2026). Apply with
`git am patches/*.patch` in a checkout of that commit.

| Patch | Change | Description file |
|---|---|---|
| 0001 | Expect the linear modifier in layout tests on Linux (test only, plus AUTHORS) | `CL-A0-layout-test-modifier.md` |
| 0002 | Give single-buffer P010 a second color plane | `CL-A1-p010-plane.md` |
| 0003 | Send a progressive, sized H.264 probe SPS | `CL-A2-h264-probe-sps.md` |
| 0004 | Support slice-based stateless H.264 decoders | `CL-A3-h264-slice-based.md` |
| 0005 | Send only references in a slice-based H.264 DPB | `CL-A4-h264-reference-dpb.md` |
| 0006 | Decode multi-slice H.264 pictures on slice-based devices | `CL-A5-h264-multi-slice.md` |
| 0007 | Send HEVC slice parameters to stateless decoders | `CL-A6-hevc-slice-params.md` |
| on-hold/0008 | Allow V4L2 decoder nodes in the desktop Linux GPU sandbox | `CL-B1-sandbox-decoder-nodes.md` |

Send 0001 first: it fixes three unit tests that fail in a Linux build, and
0002 extends the same test file. 0003 and 0007 stand alone. 0004, 0005 and
0006 are one feature in three steps: 0004 adds the slice-based mode, 0005 fixes
the reference list it sends, 0006 adds pictures with more than one slice. A
slice-only driver needs all three.

0008 is on hold and is not part of this upload set. It belongs with the
desktop-V4L2 proposal in `CL-B-desktop-v4l2.md`, needs its own bug first, and
applies on top of 0001-0007.

`patches/follow-up/0001` (`CL-F1-capture-buffers.md`) is new and was not
reviewed. The hardware tests found that seeking an H.264 stream with B-frames
can hang on desktop Linux, with or without this set, because the decoder gets
too few driver-allocated buffers. It is a one-line fix, independent of the
rest; decide whether to send it.

Each description file holds the Gerrit description, the files, the reviewers,
the unit tests and the results. Each description has two placeholders to
replace before upload: the AI-disclosure sentence and the tracking bug (0001
already names bug 526240284).

## Results in short

All patches were tested together as one build on an Apple M2 Max (Asahi
Linux, AVD decoder); the details are in each `CL-*.md`.

- All 28 V4L2 unit tests pass.
- Every H.264, HEVC and VP9 test clip plays to the end on the hardware
  decoder, with every sandbox flag on. (The GPU seccomp sandbox does not
  engage on this machine; see `CL-B-desktop-v4l2.md`.)
- Picture: H.264 (one slice, 4 slices, up to 29 slices, B-frames,
  weighted-prediction fades), HEVC 8- and 10-bit (fades included) and VP9
  profile 2 decode to the same pixels as FFmpeg, up to a fixed colour
  conversion in the hardware frame path (see `CL-A0-*.md`, "Results").
- `video_decode_accelerator_tests` does not run on desktop Linux at this
  base, for reasons in the test itself; the picture check replaces it.

Problems found that this set does not fix, all also seen without this
round's changes:

- 8-bit VP9 plays but decodes to a flat frame on AVD, also with unpatched
  main. 10-bit VP9 is correct. Either the kernel driver or Chromium's
  unchanged VP9 path; not investigated.
- Seeks in H.264 streams with B-frames can hang (the follow-up fixes it).
- A stream that changes resolution mid-stream stops with a decode error at
  the change, for H.264 and HEVC. The cause is not known.
- Hardware frames are converted to RGB with BT.601 coefficients even when the
  stream is BT.709, so colours differ slightly from software decode. This is
  in the GPU frame path, not in the decoder.

## Tests

`tests/` holds the scripts behind the results. `run-tests.sh` runs them all;
its header lists the environment it needs.

- `sr-play.py` plays clips in Chrome with every sandbox on and a throwaway
  profile, and reports the decoder, frames, drops and CPU.
- `sr-picture.py` seeks a `<video>` to several frames, reads each displayed
  frame with WebCodecs (and, with `PICTURE_CANVAS=1`, through a 2D canvas),
  and compares it with FFmpeg's software decode of the same frame: md5
  against every FFmpeg frame and PSNR against the nearest one. It also logs
  how long each seek took.
- `pixmap.py` (NV12) and `pixmap10.py` (RGBX against a 10-bit reference)
  check whether each Chrome pixel is a fixed function of FFmpeg's YUV value at
  that pixel. A decode error breaks that; a colour conversion does not.
  `run-tests.sh analyse` runs them on the frames `sr-picture.py` saved.
- `make-fade-clips.sh` makes HEVC (x265) and H.264 (x264) clips with colour
  fades, so that most P frames use weighted prediction, chroma included.
- `make-reschange-clips.sh` makes H.264 and HEVC streams that change size
  mid-stream (360p, 720p, 360p), each part starting with an IDR picture.
  `run-tests.sh reschange` muxes them to MP4 and plays them.
- `make-vdat-json.py` turns a clip into the elementary stream and the JSON
  (with FFmpeg frame md5s) that `video_decode_accelerator_tests` reads, for
  platforms where that test runs.

## Build and toolchain

The test build used `use_v4l2_codec=true`, `use_vaapi=false`,
`proprietary_codecs=true` and `ffmpeg_branding="Chrome"`, with system clang
23.1.3 and rustc 1.99.0 on aarch64 (Apple M2 Max, Asahi Linux, kernel 7.2).
Chromium's clang plugins cannot run in that build, because Chromium ships its
clang for x86-64 hosts only.

So every changed file was also compiled separately with Chromium's own clang
and its plugins (find-bad-constructs, raw-ptr-plugin, unsafe-buffers) and
`-Werror`, syntax only (`-fsyntax-only`), for an aarch64 target, against the
test build's generated headers. That catches the plugin errors a bot would
report. It is not a full bot build and links nothing; a CQ dry run is still
the real check.
