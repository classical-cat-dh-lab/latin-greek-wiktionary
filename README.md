# Latin & Ancient Greek dictionary

A fast, offline-capable, Wiktionary-derived dictionary by Classical Cat DH Lab.
Paste a passage and select individual words to explore definitions, grammatical
readings and dictionary links. The runtime uses a finite index, without a server
lookup or runtime morphological analysis.

**[Open the reader](https://data.latingreek.org/wiktionary/)** ·
**[Download the release](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/tag/v0.1.0-beta.1)**

Version **0.1.0-beta.1** freezes the first backend contract for a student trial.
Presentation is provisional and will be revised before 1.0. The current support
target is maintained Safari, Chrome, Firefox and Edge on macOS 15 or later.
The release evidence distinguishes that target from the OS actually tested.

## Downloads and reuse

Release attachments provide a gzip-compressed SQLite database, its schema and
field guide, the complete static reader, fixed raw source slices and revision
witnesses, and the matching software source. Large data files are release assets,
not Git history. `SHA256SUMS` identifies the exact attachments. The Zenodo Dataset
record archives the actual data and supporting attachments; see `CITATION.cff`.

Read [the backend contract](source/specs/backend-contract.md),
[normalization rules](source/specs/normalization.md), [build instructions](BUILD.md),
[licence map](LICENSE.md) and [attribution](NOTICE.md). Open the decompressed
`dictionary.sqlite` with any compatible SQLite tool. `entry_locator` gives stable
source locators. Original source JSONL bytes are recoverable from `entry.raw_zlib`.
The static reader exposes the named `lexical-entry/1` semantic projection.

The fixed base was captured on 20 September 2026, with documented source reviews
through 30 September. All retained source candidates remain available. Known
source gaps and ambiguous relations are explicitly marked; no missing definitions
were invented. This is neither a complete historical vocabulary nor a guarantee
that every Wiktionary content channel was captured. Genuine uncertainty survives.

Choose **Save offline** and wait for **Ready offline**. Browser storage can be
reclaimed; verifying the saved copy while online restores missing or damaged files.
Updates wait for explicit activation. The text-only package excludes multimedia
and externally linked content. Your passage stays on your device.
