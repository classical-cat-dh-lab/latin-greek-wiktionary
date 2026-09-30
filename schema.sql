CREATE INDEX change_rule ON change(rule);
CREATE INDEX entry_lang_line ON entry(lang,source_line);
CREATE INDEX entry_page ON entry(page,lang);
CREATE INDEX form_entry ON form(entry_id);
CREATE INDEX form_surface_form ON form_surface(form_id);
CREATE INDEX form_surface_word ON form_surface(lang,surface);
CREATE INDEX head_exact ON head(lang,exact);
CREATE INDEX head_quantity ON head(lang,quantity);
CREATE INDEX issue_kind ON issue(kind);
CREATE INDEX link_occurrence_entry ON link_occurrence(entry_id);
CREATE INDEX ownership_root ON ownership(root_id);
CREATE INDEX relation_entry ON relation(entry_id);
CREATE INDEX relation_sense ON relation(sense_id);
CREATE INDEX sense_entry ON sense(entry_id);
CREATE INDEX surface_exact ON surface(lang,exact);
CREATE INDEX surface_quantity ON surface(lang,quantity);
CREATE INDEX surface_reading ON surface(lang,reading);
CREATE INDEX surface_spelling ON surface(lang,spelling);
CREATE INDEX surface_tolerant ON surface(lang,tolerant);
CREATE TABLE change(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
 pointer TEXT NOT NULL, rule TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE entry(id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES source(id),
 source_line INTEGER NOT NULL, lang TEXT NOT NULL, word TEXT NOT NULL, page TEXT NOT NULL,
 pos TEXT NOT NULL, etymology TEXT, headword TEXT NOT NULL, role TEXT NOT NULL,
 raw_sha256 TEXT NOT NULL, raw_zlib BLOB NOT NULL, UNIQUE(source_id,source_line));
CREATE TABLE form(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
 ordinal INTEGER NOT NULL, surface TEXT NOT NULL, role TEXT NOT NULL,
 table_id INTEGER REFERENCES table_context(id), grammar TEXT NOT NULL,
 UNIQUE(entry_id,ordinal));
CREATE TABLE form_surface(lang TEXT NOT NULL, surface TEXT NOT NULL,
 form_id INTEGER NOT NULL REFERENCES form(id));
CREATE TABLE head(lang TEXT NOT NULL, text TEXT NOT NULL, exact TEXT NOT NULL,
 quantity TEXT NOT NULL, entry_id INTEGER NOT NULL REFERENCES entry(id), kind TEXT NOT NULL);
CREATE TABLE issue(id INTEGER PRIMARY KEY, entry_id INTEGER REFERENCES entry(id),
 pointer TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE link(id INTEGER PRIMARY KEY, target TEXT NOT NULL, page TEXT NOT NULL,
 lang TEXT NOT NULL, anchor TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE link_occurrence(entry_id INTEGER NOT NULL REFERENCES entry(id),
 pointer TEXT NOT NULL, label TEXT NOT NULL, link_id INTEGER NOT NULL REFERENCES link(id));
CREATE TABLE link_target(link_id INTEGER NOT NULL REFERENCES link(id),
 entry_id INTEGER NOT NULL REFERENCES entry(id), PRIMARY KEY(link_id,entry_id)) WITHOUT ROWID;
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE ownership(entry_id INTEGER NOT NULL REFERENCES entry(id),
 root_id INTEGER NOT NULL REFERENCES entry(id), depth INTEGER NOT NULL, path TEXT NOT NULL,
 status TEXT NOT NULL, PRIMARY KEY(entry_id,root_id,path)) WITHOUT ROWID;
CREATE TABLE redirect(id INTEGER PRIMARY KEY, source_line INTEGER NOT NULL, title TEXT NOT NULL,
 target TEXT NOT NULL, final_page TEXT NOT NULL, anchor TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE relation(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
 sense_id INTEGER REFERENCES sense(id), pointer TEXT NOT NULL, kind TEXT NOT NULL,
 target TEXT NOT NULL, hints TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE relation_review(relation_id INTEGER PRIMARY KEY REFERENCES relation(id),
 disposition TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE relation_target(relation_id INTEGER NOT NULL REFERENCES relation(id),
 entry_id INTEGER NOT NULL REFERENCES entry(id), method TEXT NOT NULL,
 PRIMARY KEY(relation_id,entry_id)) WITHOUT ROWID;
CREATE TABLE reviewed_owner(entry_id INTEGER NOT NULL REFERENCES entry(id),
 root_id INTEGER NOT NULL REFERENCES entry(id), evidence TEXT NOT NULL,
 PRIMARY KEY(entry_id,root_id)) WITHOUT ROWID;
CREATE TABLE sense(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
 ordinal INTEGER NOT NULL, role TEXT NOT NULL, glosses TEXT NOT NULL, display_origin TEXT NOT NULL,
 grammar TEXT NOT NULL, UNIQUE(entry_id,ordinal));
CREATE TABLE source(id INTEGER PRIMARY KEY, lang TEXT NOT NULL, path TEXT NOT NULL,
 sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, records INTEGER NOT NULL);
CREATE TABLE source_review(entry_id INTEGER PRIMARY KEY REFERENCES entry(id), detail TEXT NOT NULL);
CREATE TABLE surface(id INTEGER PRIMARY KEY, lang TEXT NOT NULL, text TEXT NOT NULL,
 exact TEXT NOT NULL, reading TEXT NOT NULL, tolerant TEXT NOT NULL, spelling TEXT NOT NULL,
 quantity TEXT NOT NULL,
 UNIQUE(lang,text));
CREATE TABLE table_context(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES entry(id),
 ordinal INTEGER NOT NULL, source TEXT, header TEXT NOT NULL, template TEXT);
CREATE VIEW entry_locator AS SELECT e.id,
            'sha256:'||s.sha256||'/line/'||e.source_line AS locator,
            e.raw_sha256 AS record_sha256 FROM entry e JOIN source s ON s.id=e.source_id;
