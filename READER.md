# Run the offline reader

Extract this archive and, from its directory, run:

```sh
python3 serve.py wiktionary --port 8774
```

Open http://127.0.0.1:8774/wiktionary/ in a supported browser. Choose Save offline
and wait for Ready offline before stopping the server. The server binds only to
this computer; lookup stays in the browser. Python's standard library is enough.
Opening index.html directly with a file URL does not support the reader's workers.

This is version 0.1.1. See RELEASE.md, RELEASE-MANIFEST.json and NOTICE.md for
changes, the unchanged data edition, download checksums and attribution.
