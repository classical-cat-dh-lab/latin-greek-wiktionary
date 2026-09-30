#!/usr/bin/env python3
"""Serve a built package at its publication path, on loopback only."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('site', type=Path)
parser.add_argument('--port', type=int, default=8774)
args = parser.parse_args()
if not (args.site / 'manifest.json').is_file():
    parser.error('A complete built site is required.')


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.mjs': 'text/javascript', '.gz': 'application/octet-stream',
                      '.webmanifest': 'application/manifest+json'}

    def do_GET(self):
        if not urlsplit(self.path).path.startswith('/wiktionary/'):
            self.send_error(404)
            return
        self.path = '/' + self.path[len('/wiktionary/'):]
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_HEAD(self):
        if not urlsplit(self.path).path.startswith('/wiktionary/'):
            self.send_error(404)
            return
        self.path = '/' + self.path[len('/wiktionary/'):]
        super().do_HEAD()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', args.port),
                            partial(Handler, directory=str(args.site.resolve())))
print(f'http://127.0.0.1:{server.server_port}/wiktionary/', flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
