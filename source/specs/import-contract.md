# Import contract v1

Status: step-2 implementation contract, 2026-09-30. Authority: PROJECT.md.

## Scope and identities

Read the hash-pinned English-Wiktionary Latin/Ancient Greek raw slices and the
language-neutral redirect capture. Wiktionary, not the extractor, is authoritative.
Validate byte size and SHA-256 before constructing a new database. Source files
are immutable. A failed build cannot replace an already completed database.

A source occurrence is identified by source hash and line number. Entry, sense,
form and relation ordinal identities are distinct. Never merge occurrences by
page/POS/etymology or by normalized spelling. Preserve each original JSONL line
losslessly as a compressed payload, including unknown fields, source annotations,
quotation/reference data, and original ordering. This is the internal evidence
database, not the eventual browser delivery format.

The SQLite projection contains:

| Entity | Contract |
|---|---|
| source / entry | Pinned input and occurrence locator; page, language, POS, etymology, headword, reader role and complete raw payload |
| sense | Ordered gloss path, display fallback, tags and non-Cartesian grammatical representation |
| table_context / form | Original table boundary/header/template; every form-array item receives a role and retains its ordinal |
| head | Title/canonical/source-page aliases used for relation resolution, separate from lookup keys |
| surface / form_surface | Admitted literal word spellings, normalized keys and every contributing occurrence |
| relation / relation_target | Original assertion plus qualified zero/one/many target occurrences, resolution evidence and state |
| link / link_target | Source display/target/pointer and local page-section navigation candidates or explicit nonlocal/unresolved state |
| redirect | Original neutral redirect and chain outcome; no language guessed from spelling |
| ownership | Precomputed form-only-to-lexical paths; no runtime morphology or forced homograph merge |
| issue / change | Grouped exceptions and consequential applied rules with occurrence locators |
| source_review / reviewed_owner | Hash-guarded editorial evidence and explicitly reviewed owner edges; separate from untouched raw assertions |

Integer database IDs are build-local. The source hash plus occurrence locator is
the reproducible reference; no permanent universal lexeme identity is claimed.

## Source admission and cleaning

- Keep every raw record and every form occurrence, including exact duplicates.
  Deduplicate only identical lookup contributions; source occurrences remain distinct.
- Classify table/template/class markers, absence markers, romanization,
  pronunciation, periphrastic recipes, explicit multiword content, affixes/symbols,
  and word forms separately. Formula expansion is prohibited.
- Recover Greek tense from qualified conjugation-table context only within its
  boundary and matching source field. Preserve dialect and all header wording.
  Separate morphological tense from present/imperfect/future *meaning* where the
  source heading establishes that distinction; never flatten those into two tenses.
- Remove an article wrapper from a Greek nominal table form only with the expected
  table family and source links demonstrating the article and remaining word.
  Store the wrapper and rule; do not split arbitrary phrases into new forms.
- Source-encoded movable-nu notation may yield its two explicitly represented
  single-word spellings. This is notation decoding, not paradigm generation.
- Separate leaked Latin-script Greek transliterations from Greek orthographic
  forms under qualified table contexts. Retain other foreign/unknown strings as
  content with an explicit role instead of silently deleting them.
- Recover a missing display gloss from existing raw gloss/qualifier text while
  preserving uncertainty. Never manufacture an absent definition.
- Apply source-located semantic corrections only with expected-value guards.
  The reviewed false `form_of` cases remain definitions or cross-language/ending
  explanations rather than same-language inflection edges.
- Preserve flat feature bundles without Cartesian expansion. Extract correlated
  person/number alternatives only where the gloss explicitly enumerates them;
  otherwise keep the bundle and wording for presentation.

Finite person/number labels leaked onto infinitives are removed only within
qualified conjugation templates and matching table sources. Preserve source tags
in the raw record and record the repair. Recognized head/table prose and bounded
suffix labels are separated from word surfaces; arbitrary mixed-script spellings
are not automatically rewritten.

The 2026-09-30 review overlay is pinned in
[`source-repairs-20260930.json`](../evidence/source-repairs-20260930.json).
Each record must match its language, source line and raw SHA-256. A stale or unused
review aborts the build. New Wiktionary revision evidence is dated separately from
the base dump. Explicitly reviewed optional-letter notation, table features and
script typos may change the projection; they never change the original payload.
Classification of non-word content is distinct from a linguistic correction.
Absent source definitions and unavailable source pages remain different states.
Etymology-based owner recovery does not erase a source's uncertain sense.

## Relations, internal links and ownership

Resolve lexical assertions using source link evidence, canonical spellings,
quantity-only target aliases and relevant POS. Reader normalization is not an
identity resolver: case/diacritic/spelling tolerance cannot establish lexical
identity. Keep multiple supported target occurrences as candidates.

If no source head resolves, an explicitly supplied paradigm surface can identify
candidate containing entries. Record that weaker `attested_paradigm_surface`
method separately; it does not establish a new lexeme or invent a definition.

Conjunction/qualifier cleanup requires matching source links or independently
present headwords plus the original grammatical description. Never split every
`and`, comma or parenthesis in arbitrary definition prose. A syntactic target
split retains its original assertion and qualifiers. Explicit non-target-language
links do not become local inflection relations.

Internal navigation has different semantics from morphological ownership. An
unqualified page link can navigate to an included page without asserting a language
or a lexical relation. Explicit other-language sections, external sites and missing
pages remain distinguishable. Follow captured redirects with cycle detection;
admit word aliases only when the redirect actually reaches included entries.
An internal link without a standalone captured page can resolve to an indexed
paradigm form under strict quantity-only spelling. Mark this `local_form`, retain
the original page/anchor, and show its candidate entries rather than pretending
the missing source page was captured. Fine-grained anchors remain source locators;
page-level navigation is not proof that an exact source section was reconstructed.

An entry with only valid form descriptions is an intermediate form-only node.
Keep its complete paradigm and grammatical evidence; precompute paths to lexical
entries. A lexicalized noun/adjective with independent senses remains independent.
Mixed entries keep their lexical senses and relation paths. An unresolved form
remains retrievable as unresolved, not silently promoted to a new lexical word.
Cycles and genuinely ambiguous targets are exposed, not guessed away.

A source-reviewed composite owner may be split into existing, POS-qualified
heads, preserving all supported targets and the original assertion. An assertion
that resolves to its own already lexical/mixed record is a local reading, not
automatically a defective ownership cycle. Actual form-only cycles remain visible.

## Completion and limits

Every input record, sense, form, relation and explicit link must be accounted for.
Validate payload round-trip hashes, counts, foreign keys, SQLite integrity, rule
guards, path termination and case-study regressions. Generate complete exception
exports and compact grouped evidence; distinguish expected ambiguity/nonlocal
references from defective extraction or missing source data.

This checkpoint qualifies a pipeline and a complete projection of the pinned
captures. It does not assert that these captures exhaust all Wiktionary channels
or that every source scholarly statement is correct. Source-capture gaps and
unresolved source cases remain named in the checkpoint report.
