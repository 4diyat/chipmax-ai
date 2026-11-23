#!/usr/bin/env python3
"""Sandbox-only preview bridge.

ai-visualizer binds 127.0.0.1 on purpose: it is a local app, and a face open to
your whole network would be a silly thing to ship. But this build runs in a
remote sandbox, where the browser is somewhere else and 127.0.0.1 means "the
viewer's own laptop", not this machine. This forwards one port so the face can
be watched from outside, and nothing else changes.

It is NOT part of ChipMax. On a real machine you never run it; the video
server is already reachable from the browser sitting next to it.

    python3 tools/preview-bridge.py [--listen 8080] [--target 8790]
"""
import argparse
import socket
import threading


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def serve(listen_port, target_port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", listen_port))
    srv.listen(64)
    print(f"preview bridge: 0.0.0.0:{listen_port} -> 127.0.0.1:{target_port}", flush=True)
    while True:
        client, _ = srv.accept()
        try:
            upstream = socket.create_connection(("127.0.0.1", target_port), timeout=5)
            upstream.settimeout(None)
        except OSError:
            client.close()
            continue
        threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
        threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, default=8080)
    ap.add_argument("--target", type=int, default=8790)
    a = ap.parse_args()
    serve(a.listen, a.target)
