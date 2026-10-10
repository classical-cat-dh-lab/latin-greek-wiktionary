# Latin & Ancient Greek dictionary

A fast, offline-capable, Wiktionary-derived dictionary by Classical Cat DH Lab.
Paste a passage and select individual words to explore definitions, grammatical
readings and dictionary links. The runtime uses a finite index, without a server
lookup or runtime morphological analysis.

**[Open the reader](https://data.latingreek.org/wiktionary/)** ·
**[Download the release](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/tag/v0.1.1)**

Version **0.1.1** fixes online lookup recovery when browser cache access fails.
It is the baseline before the planned 0.2 frontend redesign. The lexical data,
normalization and `lexical-entry/1` contract remain frozen; presentation is
provisional. Maintained Safari, Chrome, Firefox and Edge on macOS 15+ remain
the support target. See [release notes](RELEASE.md) for measured verification.

## Downloads and reuse

The [0.1.1 release](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/tag/v0.1.1)
provides the complete offline reader, software source, field guide and checksums.
The unchanged [SQLite database](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/download/v0.1.0-beta.1/wiktionary-0.1.0-beta.1.sqlite.gz)
and [original inputs and witnesses](https://github.com/classical-cat-dh-lab/latin-greek-wiktionary/releases/download/v0.1.0-beta.1/wiktionary-0.1.0-beta.1-inputs.tar.gz)
remain available under their original filenames.
[RELEASE-MANIFEST.json](RELEASE-MANIFEST.json) pins their URLs, sizes and SHA-256
values, alongside the current reader identity. Large data files are release assets,
not Git history. `SHA256SUMS` covers both new attachments and inherited data files.

The earlier Zenodo Dataset draft remains unpublished after transfer failures.
This patch does not claim a new DOI or completed Dataset archive. GitHub is the
current distribution for the website, source and data packages.

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
