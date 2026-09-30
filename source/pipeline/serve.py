#!/usr/bin/env python3
"""Serve an already compiled dictionary on loopback only."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
        '.mjs':'text/javascript', '.webmanifest':'application/manifest+json',
        '.gz':'application/octet-stream', '.woff2':'font/woff2'}
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()
    def log_message(self, *args):
        pass

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--port',type=int,default=8773)
    a=p.parse_args()
    if not (a.directory/'manifest.json').is_file():raise SystemExit('Not a compiled dictionary package')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(Handler,directory=str(a.directory.resolve())))
    print(f'Local dictionary: http://127.0.0.1:{a.port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
