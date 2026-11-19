#!/usr/bin/env python3
"""Local WebRTC relay. Sender and receiver exchange SDP on ws://127.0.0.1:8771.
Pages are served on http://127.0.0.1:8770. POST /stats is saved and printed."""
import asyncio, json, os
from pathlib import Path

try:
    from websockets.asyncio.server import serve
except ImportError:
    from websockets.server import serve

ROOT = Path(__file__).resolve().parent
# SR_FORCE_PROFILE=64001f: the receiver is told the sender's constrained
# baseline stream (42e01f) is High, and the answer is mapped back for the
# sender. A constrained baseline stream is valid input for a High decoder.
FORCE = os.environ.get("SR_FORCE_PROFILE", "")
SENT = "profile-level-id=42e01f"
PEERS = {}
QUEUES = {"sender": [], "receiver": []}
STATS = ROOT / "stats.json"

async def http_handler(reader, writer):
    try:
        req = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
    except Exception:
        writer.close()
        return
    head = req.decode("latin1", "replace")
    line = head.split("\r\n", 1)[0]
    parts = line.split(" ")
    method, path = (parts + ["", ""])[:2]
    length = 0
    for h in head.split("\r\n")[1:]:
        if h.lower().startswith("content-length:"):
            length = int(h.split(":", 1)[1].strip())
    body = b""
    if length:
        body = await reader.readexactly(length)
    if method == "POST" and (path.startswith("/stats") or path.startswith("/sender-stats")):
        name = "sender-stats.json" if path.startswith("/sender") else "stats.json"
        (ROOT / name).write_text(body.decode())
        print(("SENDER " if path.startswith("/sender") else "STATS ") + body.decode(), flush=True)
        payload = b"ok"
        ctype = "text/plain"
    else:
        name = "receiver.html" if path.startswith("/receiver") else "sender.html"
        payload = (ROOT / name).read_bytes()
        ctype = "text/html"
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: " + ctype.encode()
        + b"\r\nContent-Length: " + str(len(payload)).encode()
        + b"\r\nConnection: close\r\n\r\n" + payload
    )
    await writer.drain()
    writer.close()

async def ws_handler(ws):
    role = None
    try:
        async for raw in ws:
            msg = json.loads(raw)
            if role is None and "role" in msg:
                role = msg["role"]
                PEERS[role] = ws
                print("joined", role, flush=True)
                for raw_queued in QUEUES[role]:
                    await ws.send(raw_queued)
                QUEUES[role].clear()
                continue
            other = "receiver" if role == "sender" else "sender"
            if FORCE and "sdp" in msg:
                sdp = msg["sdp"]["sdp"]
                forced = "profile-level-id=" + FORCE
                sdp = sdp.replace(SENT, forced) if role == "sender" else sdp.replace(forced, SENT)
                msg["sdp"]["sdp"] = sdp
                raw = json.dumps(msg)
                print("munged", role, [l for l in sdp.split("\r\n") if "profile-level-id" in l], flush=True)
            peer = PEERS.get(other)
            if peer is not None:
                await peer.send(raw)
            else:
                QUEUES[other].append(raw)
    finally:
        if role and PEERS.get(role) is ws:
            PEERS.pop(role, None)

async def main():
    http = await asyncio.start_server(http_handler, "127.0.0.1", 8770)
    print("http://127.0.0.1:8770", flush=True)
    async with serve(ws_handler, "127.0.0.1", 8771):
        print("ws://127.0.0.1:8771", flush=True)
        await http.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
