#!/usr/bin/env python3
"""Picture check: frames decoded by Chrome against FFmpeg's software decode.

Usage (as root): sr-picture.py NAME CHROME PORT OUTDIR CLIP...

For each clip, a page served from 127.0.0.1 fetches the file and plays it in
a <video> from a blob URL (a file:// video is cross-origin, and VideoFrame
refuses to read it). The script seeks the <video> to a few frames and reads
each displayed frame with WebCodecs (new VideoFrame(video),
VideoFrame.copyTo). An 8-bit NV12/I420 frame is copied as is; any other
format is converted to RGBX by copyTo. FFmpeg decodes the same frame of the
clip in software into the same layout. The script reports, per frame:
  - md5 of Chrome's frame, and whether FFmpeg has a frame with the same md5
    (a bit-exact match is only possible for the YUV copy);
  - PSNR (ffmpeg psnr filter) between Chrome's frame and FFmpeg's frame with
    the nearest timestamp.
If the WebCodecs copy comes back blank (a failed GPU readback), the frame is
flagged blank_readback and also read through a 2D canvas as RGBA, which is
compared with FFmpeg's BT.709 RGB conversion by PSNR only.
Raw frames are kept in OUTDIR. Prints PICTURE_DONE at the end.

Environment:
  CHROME_USER   user that runs Chrome (needs a Wayland session); required
  PICK          frame positions as fractions of the clip (default
                "0.02,0.26,0.51,0.97")
  SR_EXTRA      more Chrome switches, space separated
  PICTURE_CANVAS=1  always add the canvas readback
  PICTURE_SEEK_MS   how long a seek may take (default 10000)
"""
import base64
import hashlib
import json
import os
import pwd
import shlex
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from websockets.sync.client import connect

NAME, CHROME, PORT, OUTDIR = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
CLIPS = sys.argv[5:]
USER = os.environ["CHROME_USER"]
PW = pwd.getpwnam(USER)
RUN = f"/run/user/{PW.pw_uid}"
ROOT = os.path.join(PW.pw_dir, ".cache", "sr-picture", NAME)
PROFILE = os.path.join(ROOT, "prof")
ERR = os.path.join(ROOT, "chrome.err")
BASE = f"http://127.0.0.1:{PORT}"
PICK = [float(x) for x in os.environ.get("PICK", "0.02,0.26,0.51,0.97").split(",")]
CLASS = "sr-picture-" + NAME
FORCE_CANVAS = os.environ.get("PICTURE_CANVAS") == "1"
SEEK_MS = int(os.environ.get("PICTURE_SEEK_MS", "10000"))

PLAYERS = r"""(async () => {
  const out = [];
  for (const li of [...document.querySelectorAll('#player-list .tree-item')]) {
    (li.querySelector('.tree-item-header') || li).click();
    await new Promise((r) => setTimeout(r, 150));
    const props = {};
    for (const tr of document.querySelectorAll('#player-property-table tr')) {
      const td = tr.querySelectorAll('td');
      if (td.length >= 2) props[td[0].innerText.trim()] = td[1].innerText.trim().slice(0, 220);
    }
    out.push(props);
  }
  return out;
})()"""

LOAD = r"""(async (i) => {
  const v = document.querySelector('video');
  const blob = await (await fetch('/clip/' + i)).blob();
  v.muted = true;
  v.src = URL.createObjectURL(blob);
  await new Promise((r, e) => { v.addEventListener('loadeddata', r, {once: true});
                                v.addEventListener('error', () => e(String(v.error && v.error.message)),
                                                   {once: true}); });
  return v.src;
})(%d)"""

GRAB = r"""(async (t, force_canvas, seek_ms) => {
  const b64 = (buf) => {
    let s = '';
    for (let i = 0; i < buf.length; i += 0x8000)
      s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const v = document.querySelector('video');
  if (!v) return {err: 'no video'};
  v.muted = true; v.pause();
  const presented = new Promise((r) => v.requestVideoFrameCallback((now, m) => r(m)));
  const t0 = performance.now();
  const seeked = new Promise((r) => { v.addEventListener('seeked', () => r(true), {once: true});
                                      v.currentTime = t; });
  if (!await Promise.race([seeked, new Promise((r) => setTimeout(() => r(false), seek_ms))]))
    return {err: 'seek did not complete in ' + seek_ms / 1000 + ' s'};
  const seek_time = Math.round(performance.now() - t0);
  const m = await Promise.race([presented, new Promise((r) => setTimeout(() => r(null), 3000))]);
  const f = new VideoFrame(v);
  const out = {t, ts: f.timestamp, format: f.format, w: f.visibleRect.width,
               h: f.visibleRect.height, cs: f.colorSpace.toJSON(), seek_ms: seek_time,
               presented: m ? m.mediaTime : null};
  try {
    let opts = {rect: f.visibleRect};
    if (f.format !== 'NV12' && f.format !== 'I420') opts.format = 'RGBX';
    out.copy = opts.format || f.format;
    const buf = new Uint8Array(f.allocationSize(opts));
    out.layout = await f.copyTo(buf, opts);
    out.data = b64(buf);
    const n = opts.format ? buf.length : out.w * out.h;
    if (force_canvas || !buf.subarray(0, n).some((x) => x)) {
      // Blank readback: read the same picture through a 2D canvas instead.
      const c = new OffscreenCanvas(out.w, out.h);
      const x = c.getContext('2d');
      x.drawImage(v, 0, 0, out.w, out.h);
      out.canvas = b64(new Uint8Array(x.getImageData(0, 0, out.w, out.h).data.buffer));
    }
  } catch (e) { out.err = String(e); }
  f.close();
  return out;
})(%s, %s, %d)"""


class ClipServer(BaseHTTPRequestHandler):
    """/ is a page with one <video>; /clip/N is the Nth clip."""

    def do_GET(self):
        if self.path == "/":
            body, ctype = b"<!doctype html><video muted></video>", "text/html"
        elif self.path.startswith("/clip/") and self.path[6:].isdigit() and \
                int(self.path[6:]) < len(CLIPS):
            body, ctype = open(CLIPS[int(self.path[6:])], "rb").read(), "application/octet-stream"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def session_env():
    wl = sorted(n for n in os.listdir(RUN) if n.startswith("wayland-") and not n.endswith(".lock"))[0]
    env = {"XDG_RUNTIME_DIR": RUN, "WAYLAND_DISPLAY": wl,
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={RUN}/bus", "HOME": PW.pw_dir}
    hypr = os.path.join(RUN, "hypr")
    if os.path.isdir(hypr):
        env["HYPRLAND_INSTANCE_SIGNATURE"] = sorted(
            os.listdir(hypr), key=lambda n: os.path.getmtime(os.path.join(hypr, n)))[-1]
    return env


def http(path, method="GET"):
    with urllib.request.urlopen(urllib.request.Request(BASE + path, method=method), timeout=10) as r:
        body = r.read()
    try:
        return json.loads(body or b"null")
    except ValueError:
        return body.decode(errors="replace")


def up():
    try:
        http("/json/version")
        return True
    except Exception:
        return False


def evaluate(ws_url, expr, timeout=90):
    ws = connect(ws_url, max_size=None, open_timeout=10, legacy=True)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    end = time.time() + timeout
    try:
        while time.time() < end:
            msg = json.loads(ws.recv(timeout=max(0.1, end - time.time())))
            if msg.get("id") == 1:
                r = msg.get("result", {})
                if r.get("exceptionDetails"):
                    return {"err": r["exceptionDetails"].get("text")}
                return r.get("result", {}).get("value")
    finally:
        ws.close()
    raise TimeoutError(expr[:40])


def frame_times(clip):
    """Presentation times of the video frames, from packet timestamps."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "packet=pts_time", "-of", "csv=p=0", clip],
                         capture_output=True, text=True, check=True).stdout
    return sorted(float(x) for x in out.split() if x not in ("", "N/A"))


def ffmpeg_frame(clip, index, pix_fmt, path, cs=None):
    vf = f"select=eq(n\\,{index})"
    if pix_fmt == "rgba":
        # The matrix and range Chrome reports for the frame.
        cs = cs or {}
        matrix = {"smpte170m": "bt601", "bt470bg": "bt601", "bt2020-ncl": "bt2020"}.get(
            cs.get("matrix"), "bt709")
        rng = "full" if cs.get("fullRange") else "limited"
        vf += (f",scale=in_color_matrix={matrix}:in_range={rng}:out_range=full"
               ":flags=bilinear+accurate_rnd+full_chroma_int,format=rgba")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", vf, "-frames:v", "1",
                    "-f", "rawvideo", "-pix_fmt", pix_fmt, path], check=True)


def ffmpeg_md5s(clip, pix_fmt):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-map", "0:v:0", "-noautoscale",
                          "-f", "framemd5",
                          "-pix_fmt", pix_fmt, "-"], capture_output=True, text=True, check=True).stdout
    return [line.split(",")[-1].strip() for line in out.splitlines() if line and line[0] != "#"]


def psnr(a, b, pix_fmt, w, h):
    r = subprocess.run(["ffmpeg", "-v", "info", "-hide_banner",
                        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", f"{w}x{h}", "-i", a,
                        "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", f"{w}x{h}", "-i", b,
                        "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True)
    line = [x for x in r.stderr.splitlines() if "PSNR" in x]
    return line[-1].split("PSNR", 1)[1].strip() if line else "psnr failed: " + r.stderr[-200:]


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), ClipServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    page = f"http://127.0.0.1:{server.server_address[1]}/"
    subprocess.run(["rm", "-rf", ROOT], check=True)
    subprocess.run(["runuser", "-u", USER, "--", "mkdir", "-p", PROFILE], check=True)
    if up():
        sys.exit(f"port {PORT} already in use")
    env = session_env()
    args = [CHROME, "--enable-gpu", "--use-gl=angle", "--use-angle=gles-egl",
            "--render-node-override=/dev/dri/renderD128", "--enable-logging=stderr",
            "--vmodule=v4l2_video_decoder=1,v4l2_video_decoder_delegate_h264=1,"
            "v4l2_video_decoder_delegate_h265=1,v4l2_video_decoder_backend_stateless=1",
            "--remote-debugging-port=" + str(PORT), "--user-data-dir=" + PROFILE,
            "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble",
            "--class=" + CLASS, "--ozone-platform=wayland", "--window-size=640,360"]
    args += shlex.split(os.environ.get("SR_EXTRA", ""))
    args.append("about:blank")
    cmd = ["runuser", "-u", USER, "--", "env"] + [f"{k}={v}" for k, v in env.items()] + args
    log = open(ERR, "w")
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(CHROME), stdout=log, stderr=log)
    try:
        for _ in range(60):
            if up():
                break
            time.sleep(0.5)
        else:
            sys.exit("chrome did not open the debug port")
        if "HYPRLAND_INSTANCE_SIGNATURE" in env:
            subprocess.run(["runuser", "-u", USER, "--", "env"] +
                           [f"{k}={v}" for k, v in env.items()] +
                           ["hyprctl", "dispatch", "movetoworkspacesilent", "1,class:" + CLASS],
                           capture_output=True)
        print("version", http("/json/version").get("Browser"), flush=True)
        mi = http("/json/new?chrome://media-internals", method="PUT")
        time.sleep(1)
        for ci, clip in enumerate(CLIPS):
            base = os.path.basename(clip)
            times = frame_times(clip)
            n = len(times)
            dur = (times[-1] - times[0]) / max(n - 1, 1)
            tid = http("/json/new?" + page, method="PUT")["id"]
            ws_url = next(x for x in http("/json/list") if x["id"] == tid)["webSocketDebuggerUrl"]
            http("/json/activate/" + tid)
            time.sleep(1)
            src = evaluate(ws_url, LOAD % ci, timeout=180)
            if not isinstance(src, str):
                print(base, "load failed:", src, flush=True)
                http("/json/close/" + tid)
                continue
            md5s = {}
            for p in PICK:
                k = min(n - 1, max(0, int(round(p * (n - 1)))))
                # Middle of frame k on the media timeline Chrome uses, which
                # starts at the first frame.
                t = times[k] - times[0] + dur / 2
                g = evaluate(ws_url, GRAB % (json.dumps(t), json.dumps(FORCE_CANVAS), SEEK_MS),
                             timeout=SEEK_MS / 1000 + 60)
                if not g or g.get("err") or not g.get("data"):
                    print(base, f"frame={k}", "grab failed:", (g or {}).get("err"), flush=True)
                    continue
                raw = base64.b64decode(g["data"])
                pix = {"NV12": "nv12", "I420": "yuv420p"}.get(g["copy"], "rgba")
                w, h = g["w"], g["h"]
                cpath = os.path.join(OUTDIR, f"{base}.f{k}.chrome.{pix}")
                open(cpath, "wb").write(raw)
                # FFmpeg frame with the nearest timestamp.
                ts = g["ts"] / 1e6 + times[0]
                kk = min(range(n), key=lambda i: abs(times[i] - ts))
                fpath = os.path.join(OUTDIR, f"{base}.f{kk}.ffmpeg.{pix}")
                ffmpeg_frame(clip, kk, pix, fpath, g.get("cs"))
                md5 = hashlib.md5(raw).hexdigest()
                exact = ""
                # A failed GPU readback gives a synthetic frame: luma all 0
                # (NV12/I420) or every byte 0 (RGBX), never a decoded picture.
                if not any(raw[:w * h] if pix != "rgba" else raw):
                    exact = " blank_readback"
                if pix != "rgba":
                    if pix not in md5s:
                        md5s[pix] = ffmpeg_md5s(clip, pix)
                    hits = [i for i, m in enumerate(md5s[pix]) if m == md5]
                    exact += f" bitexact_ffmpeg_frames={hits}" if hits else " bitexact=none"
                print(base, f"want={k} seek_ms={g.get('seek_ms')} got_ts={g['ts']}",
                      f"presented={g.get('presented')}",
                      f"ffmpeg_frame={kk}", f"{w}x{h}",
                      f"format={g['format']} copy={g['copy']}", f"md5={md5}{exact}",
                      "PSNR", psnr(cpath, fpath, pix, w, h), flush=True)
                if g.get("canvas"):
                    cv = os.path.join(OUTDIR, f"{base}.f{k}.chrome-canvas.rgba")
                    open(cv, "wb").write(base64.b64decode(g["canvas"]))
                    fv = os.path.join(OUTDIR, f"{base}.f{kk}.ffmpeg.rgba")
                    ffmpeg_frame(clip, kk, "rgba", fv, g.get("cs"))
                    print(base, f"want={k} canvas_rgba cs={json.dumps(g.get('cs'))}", "PSNR",
                          psnr(cv, fv, "rgba", w, h), flush=True)
            # The player's properties, read while its tab is still open.
            mi_ws = next(x for x in http("/json/list") if x["id"] == mi["id"])
            http("/json/activate/" + mi["id"])
            time.sleep(1.5)
            found = None
            players = evaluate(mi_ws["webSocketDebuggerUrl"], PLAYERS) or []
            for props in players:
                if props.get("url", "").strip('"') == src:
                    found = props
            if not found:
                print("players", src, json.dumps(players)[:600], flush=True)
            print("decoder", base, json.dumps({k: (found or {}).get(k) for k in (
                "kVideoDecoderName", "kIsPlatformVideoDecoder")}), flush=True)
            http("/json/close/" + tid)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("PICTURE_DONE", flush=True)


if __name__ == "__main__":
    main()
