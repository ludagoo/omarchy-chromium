#!/usr/bin/env python3
"""Writes ~/smartroom-chromium-upstream/CL-*.md from the commit messages in
split/msg and the per-CL facts below. Rerun after a message changes."""
import os, re, subprocess, tempfile

R = os.path.expanduser("~/smartroom-chromium-upstream")
REPO = {"a": os.path.join(R, "split/repo"), "b": os.path.join(R, "split/repo-b")}

CLS = [
    ("A0", "layout-test-modifier", "0.txt", "a", 1,
     "Test-only. Send first: A1 extends the same test file.",
     "media_unittests --gtest_filter='V4L2UtilsTest.*'",
     "Not from the 148 port. Found when the unit tests first ran on main in a Linux "
     "build (19 Nov): the NV12, NV12M and YUV420 layout tests fail because "
     "V4L2FormatToVideoFrameLayout() sets DRM_FORMAT_MOD_LINEAR on Linux."),
    ("A1", "p010-plane", "1.txt", "a", 2, "Independent of the others.",
     "media_unittests --gtest_filter='V4L2UtilsTest.*P010*'",
     "On 148 (patch 020): HEVC Main 10 and VP9 profile 2 frames map; without it the "
     "frame layout has one plane and is rejected."),
    ("A2", "coded-size-probe", "2.txt", "a", 3, "Independent of the others.",
     "media_unittests --gtest_filter='V4L2UtilsTest.*'",
     "On 148 (patch 018): AVD keeps a 64x64 coded format without it, rejects the probe "
     "SPS, lists no CAPTURE format, and decoder init fails."),
    ("A3", "h264-slice-based", "3.txt", "a", 4,
     "Needs nothing below it. A4 and A5 build on it.",
     "media_unittests --gtest_filter='V4L2H264SliceTest.*'",
     "On 148 (patch 017 + 019): H.264 decodes on V4L2VideoDecoder on AVD; before, "
     "every request was rejected and the player fell back to FFmpeg. The supervisor's "
     "Zoom Meeting SDK check (18 Nov, 148 build with A3-A5, /dev/video-dec0 link made "
     "by hand) decoded three inbound 320x180 H.264 streams on V4L2VideoDecoder, "
     "0 dropped, about 0.9 ms per frame."),
    ("A4", "h264-reference-dpb", "4.txt", "a", 5, "On top of A3.",
     "media_unittests --gtest_filter='V4L2H264SliceTest.*'",
     "On 148 (2d816dd): all eight test clips stay on V4L2VideoDecoder to the end "
     "(600 frames), with no AVD watchdog in the kernel log. Before, a non-reference "
     "picture kept for display could sit in front of a reference; AVD sizes its table "
     "from the ACTIVE count, the slice's index fell off the end, and the decoder hung."),
    ("A5", "h264-multi-slice", "5.txt", "a", 6, "On top of A4.",
     "media_unittests --gtest_filter='V4L2H264SliceTest.*'",
     "On 148 (multi-slice branch): 4-slice clip 120 frames, 6 dropped; 6-29 slices "
     "per picture, 120 frames, 8 dropped (the video element's count at the end of "
     "a 4 s clip); hold_capture=1 capabilities=253, only after S_FMT. A WebRTC "
     "loopback (1280x720, V4L2VideoDecoder, 268 frames, 0 dropped) did not use this "
     "path: OpenH264 sent one slice per picture."),
    ("A6", "hevc-slice-params", "6.txt", "a", 7,
     "Independent of the H.264 changes (separate delegate).",
     "media_unittests --gtest_filter='V4L2HevcSliceTest.*'",
     "On 148 (patch 017 HEVC part): HEVC Main 1080p/2160p decode on AVD; before, "
     "the driver timed out (`avd: Frame processing timed out`)."),
    ("B1", "sandbox-codec-nodes", "b1.txt", "b", 1,
     "Independent of the A changes; send it with the design proposal "
     "(CL-B-desktop-v4l2.md), not with the decode fixes.",
     "media_unittests --gtest_filter='V4L2CodecNodesTest.*'",
     "Not a fix for what broke on 148: that was our patch 011 (ChromeOS names "
     "only). On Apple silicon the GPU seccomp sandbox does not engage today "
     "(stock 157: 'InitializeSandbox() called with multiple threads', Seccomp 0), "
     "so this change matters where the sandbox does engage. See "
     "CL-B-desktop-v4l2.md."),
]


RESULTS = {}
if os.path.exists(os.path.join(R, "split/results.py")):
    exec(open(os.path.join(R, "split/results.py")).read())


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True,
                          capture_output=True, text=True).stdout


def main():
    for cl, slug, msgf, which, idx, order, unit, evidence in CLS:
        repo = REPO[which]
        msg = open(os.path.join(R, "split/msg", msgf)).read().rstrip()
        title = msg.splitlines()[0]
        upload = "\n".join(l for l in msg.splitlines()
                           if not l.startswith("Assisted-by:"))
        commits = git(repo, "rev-list", "--reverse", "HEAD~%d..HEAD" %
                      (7 if which == "a" else 1)).split()
        c = commits[idx - 1]
        stat = git(repo, "show", "--stat=100", "--format=", c).rstrip()
        files = "\n".join("    " + l.strip() for l in stat.splitlines()[:-1])
        num = idx if which == "a" else 8
        with tempfile.TemporaryDirectory() as tmp:
            out_name = git(repo, "format-patch", "-1", "--start-number", str(num),
                           "-o", tmp, c).strip()
        patch = "patches/" + os.path.basename(out_name)
        out = f"""# CL {cl}: {title}

Prepared, not uploaded. Lucas uploads after an independent review and after
the contributor agreement is on file (see REPORT.md).

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `{patch}` on branch `smartroom/upstream-main` of
  github.com/ludagoo/omarchy-chromium. Studio branch
  `{"smartroom/v4l2-upstream" if which == "a" else "smartroom/v4l2-b"}` in
  `/var/lib/srbuild/chromium-main/src`.
- Order: {order}
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).{" `content/common` needs its own owner: run `git cl owners`." if which == "b" else ""}

Files:

{files}

## Description for Gerrit

Paste this as the change description. `git cl upload` adds the `Change-Id`.
Add one sentence in Lucas's own words on which parts an AI assistant drafted.

```
{upload}
```

## Tests

- Unit: `{unit}` (built with `use_v4l2_codec=true`; no device needed).
- Try bot: `linux-v4l2-codec-rel` compiles this configuration. It does not play video.
- Hardware: see "Results on main" below.

## Evidence from the 148 port

{evidence}

## Results on main

{RESULTS.get(cl, "Pending: the Studio build of `smartroom/v4l2-test` (`out/v4l2-a`).")}
"""
        path = os.path.join(R, f"CL-{cl}-{slug}.md")
        open(path, "w").write(out)
        print(path)


if __name__ == "__main__":
    main()
