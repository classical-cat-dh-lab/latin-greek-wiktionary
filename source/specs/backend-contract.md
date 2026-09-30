# Backend contract 1 — frozen with 0.1.0-beta.1

The beta release freezes this consumer contract and the accepted source base.
A later frontend may change presentation without interpreting raw Kaikki fields,
changing normalization, or silently replacing scholarly data. A defect fix requires
an explicit revision and repeated affected checks; freezing is not a prohibition
on necessary repairs. See the release checkpoint for the exact hashes.

## Identity and entities

`lexical-entry/1` separates entry occurrences, senses, forms, table context,
relation assertions, navigation links and candidate lexical owners. A record is
not automatically an independently established lexeme. Etymology numbering is
source-local; an absent number is unassigned and does not authorize merging.

`identity.locator` is `sha256:<source-file-hash>/line/<one-based-line>`.
`recordSha256` identifies exact JSONL bytes including their newline. A sense key
adds `/senses/<zero-based-ordinal>`. Integer entry/form IDs are addresses within a
package. Never persist those IDs without its package ID. Supplementary records
have a distinct source-file identity even where line numbers repeat.

Each sense exposes `glossPath`, `sourceGlosses`, `examples`, `annotations`,
`grammar`, `role` and `definitionStatus`. The ordered gloss path preserves the
extractor's sequence; it does not prove a cross-record tree. `parentKey` is null
unless a future contract establishes that tree from source evidence. Independent
lexical definitions survive form grouping. Missing definitions, source absences,
uncertain meanings and unresolved owners remain explicit rather than invented.

Entry fields `etymologyGroup`, `pronunciations`, `metadata`, `lexicalRelations`,
`internalLinks` and `provenance` expose the remaining content. Relations retain
original target text, qualifiers, resolution status and every retained candidate.
`relationReviews` records the bounded disposition of the earlier residual queue.
`content` retains recursively filtered non-media raw fields for detailed source
inspection. Legacy tuple fields remain available for the beta reader; new display
code should prefer named fields. Form tuples are
`[id, ordinal, surface, role, tableId, grammar]`; table IDs address `tables`.

## Worker protocol

Requests carry a safe-integer `id`, optional `apiVersion: 1`, and one action:

- `init`: package, edition, version, contract and byte count.
- `lookup`: `word`, `lang` (`la` or `grc`), and `profile` (`exact`, `reading`,
  `tolerant`, `spelling`). Returns `groups`, `occurrences`, `matchedInput`.
- `entries`: positive integer `ids`. Returns complete entries in requested order.

Replies carry the same `id`, `apiVersion: 1`, and either `result` or an `error`
message with `errorCode`. Defined codes: `INVALID_REQUEST`, `UNSUPPORTED_API`,
`UNSUPPORTED_PACKAGE`, `ENTRY_NOT_FOUND`, `FILE_UNAVAILABLE`, `INTEGRITY_ERROR`,
`DICTIONARY_UNAVAILABLE`. Malformed messages without a usable ID cannot be correlated.
A valid lookup miss is an empty group list, not an exception. Sentence punctuation
fallbacks run only after the literal input misses. No phrase interpretation occurs.

Matching is exact-first, followed by the selected normalization tiers. Every
source-form occurrence survives; grouping shows each reachable lexical owner and
its original readings. Candidate owners are not disambiguated by frequency or
context. The supplied `core.mjs` determines stable tie ordering within a package.
See `normalization.md` for Unicode, Latin spelling and Greek diacritic boundaries.

## Storage and updates

The manifest pins all shell/data files, compressed sizes and SHA-256 hashes.
The package ID is derived from that inventory; the shell build also pins authored
shell inputs and data files. The service worker waits for explicit update
activation, then the reader reloads against the new package. A data-file cache hit
from another package is reusable only after verification against the new hash.
Missing bootstrap metadata is recoverable online; an incompatible edition requires
an update. Damaged files are rejected and recovered online. Offline failure never
claims a successful empty lookup or a complete saved package.

Save offline verifies every file. Browser storage can be refused or evicted;
readiness on reopening checks presence and individual reads check integrity.
Older caches are retained during upgrades to protect other tabs. This beta does
not automatically garbage-collect them; storage estimates may therefore require
additional headroom. Clearing this site's browser data removes saved dictionaries
and preferences. No user passage leaves the device.

## Portable SQLite

The downloadable database includes the relational construction schema, guarded
reviews and original JSONL records as `entry.raw_zlib` (standard zlib compression).
The source paths are portable basenames. `entry_locator` provides stable locators.
JSON-valued columns are UTF-8 JSON text; integer foreign keys remain package-local.
The accompanying `schema.sql` documents every table and index. Source records can
be reconstructed byte-for-byte in `(source_id, source_line)` order. Original media
URLs may remain in the raw evidence; no media files are bundled or downloaded.

The static reader is the semantic JSON distribution of this database. Its entries
are independently checked against source and relational records. The public
builder and guarded evidence reproduce those projections with the published raw
capture inputs; runtime versions and input hashes are recorded. SQLite file bytes
are release checksums, not a promise that all SQLite/runtime versions produce an
identical file layout.
