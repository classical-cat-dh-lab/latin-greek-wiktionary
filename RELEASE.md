# 0.1 beta — 0.1.0-beta.1

The first public student-trial release freezes backend contract `lexical-entry/1`.
It includes 960,519 source records, 1,099,358 sense records, 2,798,763 admitted
spellings and 4,930,669 indexed form occurrences. The text-only offline package is
481,538,396 bytes (459.2 MiB). The portable SQLite database is 3,982,229,504 bytes;
its gzip download is 1,222,929,658 bytes.

All original base records round-trip to their pinned source hashes. Three Greek
omissions were recovered from fixed page witnesses. Of the prior 795 unresolved
form/variant assertions, 38 English explanatory tails were suppressed as false
ownership relations and 10 qualified targets repaired. Source supplements close
additional paths. 1,013 form-only entries still have unresolved ownership; their
source text remains searchable and the uncertainty is displayed. General lexical
cross-references also retain unresolved states, including other languages outside
this edition. This is not a certification of all Wiktionary channels or scholarship.

Qualification passed 37 Python and 9 JavaScript unit cases, every source record,
every delivered entry/sense/form/relation/link, 11,195,052 full-profile queries and
22,390,104 normalization comparisons. The final shell differs from the fully
record-verified candidate only by its first-install update-button correction; all
data file hashes are identical and every final file hash was independently checked.

Actual Chrome 154.0.8037.92 and Edge 154.0.4258.48 passed 17 integration cases each;
Firefox passed 10. Tests include full saving, cancellation/resumption, rejected
corruption, quota refusal, recovery and a new browser process with the server
unavailable. Five additional lifecycle checks cover protocol errors, damaged
cache recovery, missing bootstrap recovery and explicit two-version activation.
Safari 27.0.1 GUI observations cover both languages, the new source repairs, full
saving, offline new-tab reopening and cold internal navigation. The host was
macOS 27.0.1; macOS 15/Intel execution and whole-process Safari restart were not
measured. The declared support target remains maintained macOS 15+ browsers.

Known beta boundaries: the UI is provisional; missing source meanings are not
invented; source glosspaths are not a reconstructed cross-record sense tree; older
package caches are retained during upgrades. Semantic data fields intentionally
repeat source material to keep the consumer contract explicit. Further package-size
and presentation work can be assessed after student feedback without changing the
frozen backend. No automatic upstream refresh is scheduled.

See `BACKEND-FREEZE.json`, `source/evidence/`, `NOTICE.md` and `BUILD.md`.
