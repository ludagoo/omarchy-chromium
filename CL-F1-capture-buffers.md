# Follow-up F1: Leave room for the renderer in driver-allocated buffers

Prepared, not uploaded, and not reviewed: it was written after the two
reviews, from a problem the hardware tests found. Decide whether to send it.
It is independent of A0-A6 and B1 and applies to the same base on its own.

- Base: Chromium main `98478f51939a` (18 November 2026).
- Patch: `patches/follow-up/0001-media-gpu-v4l2-Leave-room-for-the-renderer-in-driver.patch`.
- Order: any time; it touches one line of `v4l2_video_decoder.cc`, which no
  other patch here changes near that line.
- Reviewers: one of `frkoenig@chromium.org`, `nhebert@chromium.org`
  (`media/gpu/v4l2/OWNERS`).

Files:

    media/gpu/v4l2/v4l2_video_decoder.cc | 11 +++++++----

## What it fixes

On desktop Linux the decoder pipeline has no frame pool, so the V4L2 decoder
asks the driver for DPB + 2 CAPTURE buffers. Seeking a paused `<video>` in a
1080p H.264 stream with B-frames (DPB of 4, so 6 buffers) then hangs: the seek
never completes, with no error. The tests found 5 of 8 such seeks hung, with
this round's patches and with the first round's alike, so it is not caused by
them. HEVC (8 buffers there) and H.264 without B-frames seek fine.

Two checks show it is the buffer count: the same stream relabelled as level
5.1 (larger DPB, so more buffers; picture data unchanged) seeks fine, and so
does the build with this change (8 of 8 seeks, 28 to 147 ms).

## Description for Gerrit

Paste the patch's commit message. Replace the `AI-DISCLOSURE-PLACEHOLDER` line
and the bug placeholder first.

## Tests

- Compile: compiled with Chromium's own clang and its plugins, `-Werror`,
  syntax only, as for A0-A6.
- Hardware: on top of A0-A6 and B1, same machine and clips as the other CLs.
  The tested build had the same arithmetic with an earlier wording of the
  comment.
- Unit: none; the count only matters with a real renderer.
