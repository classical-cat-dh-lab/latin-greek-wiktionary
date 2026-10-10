# Build and inspect version 0.1.1

The data builder uses only Python's standard library. Qualification used Python
3.14; the manifest records its Unicode and SQLite versions. Reader code uses
native Web APIs. Node.js is needed only for JavaScript verification. There are no
third-party runtime dependencies or remote fonts.

Use the unchanged raw-input attachment pinned in RELEASE-MANIFEST.json and
extract it into this checkout. It creates
`sources/capture/`, `sources/reviews/` and `sources/raw-inventory.json`.
From the repository root:

```sh
python3 -B -m unittest discover -s source/pipeline -p 'test_*.py'
node --test source/tests/core.test.mjs source/tests/runtime.test.mjs
python3 -B source/pipeline/build.py --capture sources/capture --inventory sources/raw-inventory.json --output build/staging
python3 -B source/pipeline/verify.py build/staging/dictionary.sqlite --output build/verification
python3 -B source/pipeline/export_site.py build/staging/dictionary.sqlite --output build/reader
python3 -B source/pipeline/export_database.py build/staging/dictionary.sqlite build/database
python3 -B source/tests/export_expectations.py build/staging/dictionary.sqlite build/expectations
node source/tests/full_lookup.mjs build/reader build/expectations build/lookup.json
python3 -B source/tests/verify_delivery.py build/staging/dictionary.sqlite build/reader build/delivery.json
python3 -B source/tests/preview.py build/reader --port 8774
```

Open http://127.0.0.1:8774/wiktionary/ . A `file:` URL cannot run the offline worker.
Use new output directories; the builder refuses to overwrite existing databases.
Input hashes and guarded repair records must agree. Do not edit implementation or
review inputs during a build. Sources are never fetched by the runtime or builder.

The admitted supplemental JSONL and guarded repair overlays are versioned in
`source/evidence/`. The raw-input archive also includes the page witnesses used to
admit them. To rerun the bounded supplement extractor, place its witness directory
at `source/sources/beta-supplement-20260930/` and run the matching research script.
The original Kaikki slices can independently be recovered from the database:
iterate each source's records in line order and write `zlib.decompress(raw_zlib)`
without adding or removing bytes. Compare the file hash with `source.sha256`.

The SQLite release is a portable export with local paths removed and source
locators added. It is checked against every retained relational table. The static
reader is checked against every record, relationship and source text, plus all
index occurrences and all four normalization profiles in NFC and NFD.

For hosting, serve the static package under `/wiktionary/` over HTTPS. Serve `.mjs`
as JavaScript and `.json.gz` as `application/octet-stream` without a
`Content-Encoding` header: the application verifies and decompresses these bytes.
Do not rewrite missing assets to HTML. Keep manifest/service-worker responses
revalidated so explicit package updates can be discovered.

## Patch data reuse

Version 0.1.1 changes the query/storage runtime and release identity only.
The shipped SQLite database and raw inputs retain their 0.1.0-beta.1 filenames
and checksums. BACKEND-FREEZE.json remains that original data qualification.
RELEASE-MANIFEST.json identifies the current reader and its inherited data assets.
The portable SQLite exporter retains the frozen data-edition version; the reader
exporter emits the current application version.
