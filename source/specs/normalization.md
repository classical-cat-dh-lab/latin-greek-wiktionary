# Word lookup normalization v2

Status: initial usable construction profile, 2026-09-30. Original spellings and
all candidates remain available. This specification is an editorial choice for
retrieval, not a claim that collapsed spellings are linguistically identical.

## Profiles

All profiles retain the original input separately. Version 2 ignores discretionary
soft hyphen U+00AD for admission and retrieval, including the exact tier. This
restores the title and canonical form of `grc:3915` without changing any letters;
the original source spelling remains intact. Unicode describes this as an
intraword line-break marker in [UAX 14 §5.4](https://www.unicode.org/reports/tr14/#SoftHyphen).
No other control/format character
is removed. Use canonical normalization
(NFC/NFD); never blanket compatibility normalization (NFKC/NFKD). This distinction
follows [Unicode UAX 15](https://www.unicode.org/reports/tr15/). Record the actual
runtime Unicode database version in every build manifest rather than claiming the
latest published Unicode version was used.

| Profile | Latin | Ancient Greek |
|---|---|---|
| exact | NFC, ignoring U+00AD | NFC, ignoring U+00AD |
| reading | Lowercase; remove combining macron/breve; NFC | Same quantity/case treatment; final sigma to sigma; preserve accents, breathings, diaeresis and iota subscript |
| tolerant (initial default) | Same as reading | Additionally ignore acute/grave/circumflex and smooth/rough breathing; retain diaeresis and iota subscript |
| spelling (explicit option) | Additionally map j to i and v to u | Same as tolerant |

Reading and broader profiles equate typographic elision marks U+2019,
U+02BC and U+1FBD with ASCII apostrophe, without removing the apostrophe. This
does not expand an elided word or split an enclitic. Do not use Unicode casefold:
it may turn iota subscript into a spacing iota. Lowercase under NFD preserves it.

Exact results rank first, followed by progressively broader matches. The selected
profile sets the broadest permitted equivalence. Return the union of supported
candidates; finding an exact hit does not erase other candidates. Report the
matching tier. Quantity/case/diacritic collisions never merge source entries.

## Contrasting examples

- `amāre` and `ama\u0304re` are canonically equivalent at exact tier.
- `AMĀRE` and `amare` share a reading key; `mālum` and `malum` also collide, so
  their distinct entries/senses must survive.
- `jūs` and `ius`, or `vīta` and `uita`, meet only under the explicit spelling tier.
- `λόγος` and `λόγοσ` share a reading key. `λόγος` and `λογος` meet at tolerant tier.
- `ἤ`, `ἦ` and `ἡ` can share a tolerant key; this is search ambiguity, not identity.
- `ᾧ` retains iota subscript and does not become equivalent to `ὧ`.
- `αϊ` does not become `αι`. Diaeresis remains meaningful.
- Iota subscript/adscript expansion, Latin ae/oe ligature expansion, lunate sigma,
  accent restoration and arbitrary character deletion are not automatic v2 rules.

## Word boundaries and scope

Lookup accepts a single lexical token, optionally with source-supported initial or terminal
elision punctuation, lexical hyphens or abbreviation punctuation. Combining marks
remain attached to the preceding letter. Source entries for affixes, symbols,
reconstructions and phrases are retained separately as navigable content; an
asterisk or affix boundary is not silently removed to create an ordinary word.
Already admitted word-like heads with terminal hyphens remain searchable literally;
this includes prefix entries, not productive prefix analysis or boundary stripping.

Token admission recognizes Latin/Old Italic and Greek/Cypriot/Linear B letters
within their captured language records. This preserves already supplied historical
script forms; it neither imports another language's corpus nor transliterates
between scripts. Pure romanization remains descriptive content rather than a Greek
word key. Mixed-script debris remains separately diagnosed.

The passage interface reuses WORDS interaction, not its Latin-only input adapter.
It preserves source-supported terminal hyphens, abbreviation periods, apostrophes
and soft hyphens in the original spans. Literal dictionary spellings take priority.
Only after a miss may terminal periods or surrounding quotation marks be separated
for word lookup; the reader reports that fallback. Hyphens are never stripped. No sentence analysis, periphrastic expansion or
automatic phrase-span matching is part of this specification.

Relation resolution uses stricter source aliases and explicit evidence, not the
tolerant reader key. Tests cover idempotence, NFC/NFD correspondence, retained
iota/diaeresis, spelling opt-in, collisions and candidate preservation. Whole-build
reports measure collisions; they do not treat them as an error rate.
