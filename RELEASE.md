# v0.1.1 — Cache recovery baseline

Released 10 October 2026. This patch keeps the current dictionary presentation
and establishes the baseline for the planned v0.2 frontend redesign.

Online lookup now survives browser cache open/read failures. Initialization can
be retried after failure, and corrupt cached files can be recovered even if their
deletion fails. Recovery requests bypass the service-worker data cache and still
require the declared size and SHA-256; unavailable data is an error, not an empty
lookup result. Updates continue to require explicit activation.

The fixed source capture, source repairs, lexical ownership, normalization and
`lexical-entry/1` remain unchanged. All 5,801 dictionary data files are byte-identical
to 0.1.0-beta.1. The reader package is `e57da3e515454dff06ad`, 481,539,167 bytes
(459.2 MiB). It contains 960,519 source occurrences and 1,099,358 senses.

New attachments contain the complete offline reader with a portable local server,
the signed software source, the schema/field guide, RELEASE-MANIFEST.json and
SHA256SUMS. The unchanged SQLite and input archives remain at their original,
checksum-pinned release URLs:

- [SQLite database](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/download/v0.1.0-beta.1/wiktionary-0.1.0-beta.1.sqlite.gz)
- [Original inputs and revision witnesses](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/download/v0.1.0-beta.1/wiktionary-0.1.0-beta.1-inputs.tar.gz)

The reader manifest records application version 0.1.1. The unchanged SQLite
metadata retains data-edition version 0.1.0-beta.1; BACKEND-FREEZE.json preserves
its original qualification. RELEASE-MANIFEST.json ties these identities together.

Verification includes 37 Python and 19 JavaScript tests in the public source,
10 runtime fault checks against the packaged bytes, all 5,844 file hashes, and
an actual beta-to-0.1.1 update in Chrome. The identical r1 runtime passed 17
integration checks each in Chrome and Edge and 10 in Firefox, including complete
saving and cold browser-process restart with the server unavailable. Final-package
Safari observations are recorded in source/evidence/v0.1.1-qualification.json.
macOS 15 and Intel execution remain unmeasured; macOS 15+ maintained browsers
remain the support target.

Frontend presentation remains provisional. The existing 1,013 unresolved form
owners retain their source text and explicit status. No upstream refresh or
scholarly data revision is included. The earlier Zenodo Dataset draft remains
unpublished; this routine patch does not create or claim a new DOI.
