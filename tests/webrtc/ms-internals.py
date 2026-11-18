#!/opt/smartroom/venv/bin/python
"""Read chrome://media-internals and the sender page log. Ports are argv."""
import json, sys, time, urllib.parse, urllib.request
from websockets.sync.client import connect

PLAYERS = r"""(async () => {
  const out = [];
  const items = [...document.querySelectorAll('#player-list .tree-item')];
  for (const li of items) {
    const lab = li.querySelector('.tree-item-header') || li;
    lab.click();
    await new Promise((r) => setTimeout(r, 200));
    const props = {};
    for (const tr of document.querySelectorAll('#player-property-table tr')) {
      const td = tr.querySelectorAll('td');
      if (td.length >= 2) props[td[0].innerText.trim()] = td[1].innerText.trim().slice(0, 240);
    }
    out.push(props);
  }
  return out;
})()"""

def http(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = r.read()
        return json.loads(data or b"null")

def evaluate(ws_url, expression, await_promise=False):
    ws = connect(ws_url, max_size=None, open_timeout=10, legacy=True)
    n = 0
    def call(method, params=None, timeout=40):
        nonlocal n
        n += 1
        mid = n
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(ws.recv(timeout=timeout))
            if msg.get("id") == mid:
                return msg
        raise TimeoutError(method)
    call("Runtime.enable")
    res = call("Runtime.evaluate", {
        "expression": expression,
        "awaitPromise": await_promise,
        "returnByValue": True,
    })
    ws.close()
    result = res.get("result", {}).get("result", {})
    if "value" in result:
        return result["value"]
    return result

def main():
    recv_port = int(sys.argv[1])
    send_port = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if send_port:
        try:
            pages = http(send_port, "/json/list")
            page = next(p for p in pages if p.get("type") == "page" and "8770" in p.get("url", ""))
            log = evaluate(page["webSocketDebuggerUrl"], "document.getElementById('log').textContent")
            print("SENDER_LOG")
            print(log)
        except Exception as exc:
            print("SENDER_LOG_FAIL", exc)
    try:
        mi = http(recv_port, "/json/new?" + urllib.parse.quote("chrome://media-internals", safe=""), "PUT")
        time.sleep(2.0)
        pages = http(recv_port, "/json/list")
        page = next(p for p in pages if p.get("id") == mi.get("id"))
        text = evaluate(page["webSocketDebuggerUrl"], "document.body ? document.body.innerText.slice(0, 1500) : 'no body'")
        print("MEDIA_TEXT")
        print(text)
        players = evaluate(page["webSocketDebuggerUrl"], PLAYERS, True) or []
        print("MEDIA_INTERNALS", len(players))
        wi = http(recv_port, "/json/new?" + urllib.parse.quote("chrome://webrtc-internals", safe=""), "PUT")
        time.sleep(2.0)
        pages = http(recv_port, "/json/list")
        wpage = next(p for p in pages if p.get("id") == wi.get("id"))
        clicked = evaluate(wpage["webSocketDebuggerUrl"], r'''(() => {
          const btns = [...document.querySelectorAll('button, summary')];
          const names = btns.map((b) => (b.innerText || '').trim().slice(0, 80)).filter(Boolean);
          for (const b of btns) {
            const t = b.innerText || '';
            if (/stats|RTCPeer|expand/i.test(t)) b.click();
          }
          return names.slice(0, 30);
        })()''')
        print("WEBRTC_BUTTONS", json.dumps(clicked))
        time.sleep(1.5)
        dump = evaluate(wpage["webSocketDebuggerUrl"], r'''(() => {
          const lines = (document.body.innerText || '').split('\n').map((l) => l.trim()).filter((l) => /decoder|Decoder|codec|V4L2|FFmpeg|implement|framesDecoded|framesDropped|frameWidth/i.test(l));
          return lines.slice(0, 60);
        })()''')
        print("WEBRTC_INTERNALS")
        print("\n".join(dump or []))
        keep_keys = ("kVideoDecoderName", "kIsPlatformVideoDecoder", "kVideoTracks", "kError", "kVideoPipelineError", "url", "kFrameUrl", "kRendererName", "kIsVideoDecryptingDemuxerStream", "event")
        for props in players:
            url = props.get("url", "")
            keep = {k: v for k, v in props.items() if k in keep_keys or "ecoder" in k or "rror" in k or "frame" in k.lower() or "width" in k.lower() or "height" in k.lower()}
            keep["url"] = url[:180]
            print(json.dumps(keep))
    except Exception as exc:
        print("MEDIA_INTERNALS_FAIL", exc)

if __name__ == "__main__":
    main()
