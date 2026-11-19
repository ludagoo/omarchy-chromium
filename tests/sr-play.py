#!/usr/bin/env python3
"""Clip playback check for a Chromium build. Run as root.

Usage: sr-play.py NAME CHROME PORT CLIP...

Chrome runs as CHROME_USER (required; a user with a Wayland session) with a
throwaway profile under ~CHROME_USER/.cache/sr-upstream/NAME. On Hyprland the
window goes to workspace 1.

Environment:
  SR_SANDBOX=1        keep every sandbox on (default); 0 adds --no-sandbox
  SR_FEATURES=...     --enable-features list
  SR_DISABLE=...      --disable-features list
  SR_EXTRA="..."      more switches, space separated
  SR_HIDE=1           bind /dev/null over the decoder nodes in a private mount
                      namespace for this Chrome only (no decoder present)
  PLAY_WAIT=24        seconds per clip
Prints one line per clip, then the media-internals decoder per clip, then the
/dev/video* and /dev/media* nodes the GPU process held, then PLAY_DONE.
"""
import json, os, pwd, shlex, subprocess, sys, time, urllib.request
from websockets.sync.client import connect

NAME, CHROME, PORT, CLIPS = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
USER = os.environ["CHROME_USER"]
PW = pwd.getpwnam(USER)
RUN = f"/run/user/{PW.pw_uid}"
ROOT = os.path.join(PW.pw_dir, ".cache", "sr-upstream", NAME)
PROFILE = os.path.join(ROOT, "prof")
ERR = os.path.join(ROOT, "chrome.err")
BASE = f"http://127.0.0.1:{PORT}"
WAIT = float(os.environ.get("PLAY_WAIT", "24"))
CLASS = "sr-upstream-" + NAME
DECODER_NODES = ["/dev/video0", "/dev/media0", "/dev/video-dec0", "/dev/media-dec0"]
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


def session_env():
    wl = sorted(n for n in os.listdir(RUN) if n.startswith("wayland-") and not n.endswith(".lock"))[0]
    sig = sorted(os.listdir(os.path.join(RUN, "hypr")),
                 key=lambda n: os.path.getmtime(os.path.join(RUN, "hypr", n)))[-1]
    return {"XDG_RUNTIME_DIR": RUN, "WAYLAND_DISPLAY": wl, "HYPRLAND_INSTANCE_SIGNATURE": sig,
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={RUN}/bus", "HOME": PW.pw_dir}


def http(path, method="GET"):
    with urllib.request.urlopen(urllib.request.Request(BASE + path, method=method), timeout=10) as r:
        return json.loads(r.read() or b"null")


def up():
    try:
        http("/json/version")
        return True
    except Exception:
        return False


def evaluate(ws_url, expr):
    ws = connect(ws_url, max_size=None, open_timeout=10, legacy=True)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    end = time.time() + 60
    while time.time() < end:
        msg = json.loads(ws.recv(timeout=max(0.1, end - time.time())))
        if msg.get("id") == 1:
            ws.close()
            r = msg.get("result", {})
            if r.get("exceptionDetails"):
                return {"error": r["exceptionDetails"].get("text")}
            return r.get("result", {}).get("value")
    ws.close()
    raise TimeoutError(expr[:40])


def procs():
    out = {}
    for n in os.listdir("/proc"):
        if not n.isdigit():
            continue
        try:
            st = open(f"/proc/{n}/stat").read()
            cmd = open(f"/proc/{n}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        f = st[st.rfind(")") + 2:].split()
        out[int(n)] = (int(f[1]), int(f[11]) + int(f[12]), cmd)
    return out


def tree(root, ps):
    kids = {}
    for pid, (ppid, _, _) in ps.items():
        kids.setdefault(ppid, []).append(pid)
    seen, stack = [], [root]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.append(p)
        stack.extend(kids.get(p, []))
    return seen


def cpu(root):
    ps = procs()
    return sum(ps[p][1] for p in tree(root, ps) if p in ps)


def gpu_nodes(root):
    ps = procs()
    held = set()
    for p in tree(root, ps):
        if p in ps and "--type=gpu-process" in ps[p][2]:
            for fd in os.listdir(f"/proc/{p}/fd"):
                try:
                    t = os.readlink(f"/proc/{p}/fd/{fd}")
                except OSError:
                    continue
                if t.startswith("/dev/video") or t.startswith("/dev/media"):
                    held.add(t)
    return sorted(held)


def main():
    subprocess.run(["rm", "-rf", ROOT], check=True)
    subprocess.run(["runuser", "-u", USER, "--", "mkdir", "-p", PROFILE], check=True)
    if up():
        sys.exit(f"port {PORT} already in use")
    env = session_env()
    feats = os.environ.get("SR_FEATURES", "")
    args = [CHROME]
    if os.environ.get("SR_SANDBOX", "1") == "0":
        args.append("--no-sandbox")
    args += ["--enable-gpu", "--use-gl=angle", "--use-angle=gles-egl",
             "--render-node-override=/dev/dri/renderD128"]
    if feats:
        args.append("--enable-features=" + feats)
    if os.environ.get("SR_DISABLE"):
        args.append("--disable-features=" + os.environ["SR_DISABLE"])
    args += ["--enable-logging=stderr",
             "--vmodule=v4l2_decoder_nodes=1,v4l2_video_decoder=1,v4l2_device=1,"
             "v4l2_video_decoder_delegate_h264=1,v4l2_video_decoder_delegate_h265=1,"
             "v4l2_video_decoder_backend_stateless=1,v4l2_utils=1",
             "--remote-debugging-port=" + str(PORT), "--user-data-dir=" + PROFILE,
             "--autoplay-policy=no-user-gesture-required", "--no-first-run",
             "--no-default-browser-check", "--disable-session-crashed-bubble",
             "--class=" + CLASS, "--ozone-platform=wayland", "--ozone-platform-hint=wayland",
             "--window-size=640,360"]
    args += shlex.split(os.environ.get("SR_EXTRA", ""))
    args.append("about:blank")
    user_cmd = ["runuser", "-u", USER, "--", "env"] + [f"{k}={v}" for k, v in env.items()] + args
    if os.environ.get("SR_HIDE") == "1":
        binds = "; ".join(f"[ -e {n} ] && mount --bind /dev/null {n}" for n in DECODER_NODES)
        cmd = ["unshare", "--mount", "--propagation", "private", "bash", "-c",
               binds + "; exec " + " ".join(shlex.quote(a) for a in user_cmd)]
    else:
        cmd = user_cmd
    log = open(ERR, "w")
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(CHROME), stdout=log, stderr=log)
    try:
        for _ in range(60):
            if up():
                break
            time.sleep(0.5)
        else:
            sys.exit("chrome did not open the debug port")
        subprocess.run(["runuser", "-u", USER, "--", "env"] + [f"{k}={v}" for k, v in env.items()] +
                       ["hyprctl", "dispatch", "movetoworkspacesilent", "1,class:" + CLASS],
                       capture_output=True)
        print("version", http("/json/version").get("Browser"), "hide=" + os.environ.get("SR_HIDE", "0"),
              "sandbox=" + os.environ.get("SR_SANDBOX", "1"), flush=True)
        hz = os.sysconf("SC_CLK_TCK")
        mi = http("/json/new?chrome://media-internals", method="PUT")
        time.sleep(1)
        held = set()
        for clip in CLIPS:
            tid = http("/json/new?" + urllib.request.quote("file://" + clip, safe=":/?=&"), method="PUT")["id"]
            before, t0 = cpu(proc.pid), time.time()
            time.sleep(WAIT / 2)
            held.update(gpu_nodes(proc.pid))
            time.sleep(WAIT / 2)
            pct = (cpu(proc.pid) - before) / hz / max(time.time() - t0, 0.001) * 100.0
            t = next(x for x in http("/json/list") if x["id"] == tid)
            st = evaluate(t["webSocketDebuggerUrl"],
                          '(()=>{const v=document.querySelector("video"); if(!v) return "no video";'
                          'const q=v.getVideoPlaybackQuality(); return {size:v.videoWidth+"x"+v.videoHeight,'
                          't:+v.currentTime.toFixed(2), ended:v.ended, err:v.error&&v.error.code,'
                          'frames:q.totalVideoFrames, dropped:q.droppedVideoFrames}})()')
            print(os.path.basename(clip), json.dumps(st), "cpu_pct=%.1f" % pct, flush=True)
            try:
                urllib.request.urlopen(f"{BASE}/json/close/{tid}", timeout=5).read()
            except Exception:
                pass
            time.sleep(0.4)
        t = next(x for x in http("/json/list") if x["id"] == mi["id"])
        for pr in evaluate(t["webSocketDebuggerUrl"], PLAYERS) or []:
            url = pr.get("url", "").strip('"')
            if url.startswith("file://"):
                keep = {k: v for k, v in pr.items() if k in ("kVideoDecoderName", "kIsPlatformVideoDecoder",
                        "kError", "kVideoPipelineError") or "rror" in k}
                print("decoder", os.path.basename(url), json.dumps(keep), flush=True)
        print("gpu_nodes", " ".join(sorted(held)) or "none", flush=True)
        print("PLAY_DONE", flush=True)
    finally:
        stop(proc)


def stop(proc):
    """SIGTERM to this profile's browser process, then SIGKILL what is left."""
    if proc.poll() is not None:
        return
    ps = procs()
    mine = [p for p in tree(proc.pid, ps) if p in ps and PROFILE in ps[p][2]]
    for p in mine:
        if "--type=" not in ps[p][2]:
            try:
                os.kill(p, 15)
            except OSError:
                pass
    for _ in range(20):
        if proc.poll() is not None:
            return
        time.sleep(0.25)
    for p in mine + [proc.pid]:
        try:
            os.kill(p, 9)
        except OSError:
            pass


if __name__ == "__main__":
    main()
