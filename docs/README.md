# Documents

The three living documents are Claude docs, exported here as Markdown on 2026-10-31 and the
specification and design document again on 2026-11-01 (the drawings become text placeholders in
the export). Re-export whenever a document changes, so
that reviewers and agents work from the same text that is in the repository.

| File | Document | Status |
| --- | --- | --- |
| `feasibility-study.md` | Python → C++26 by intent-level AST passes: feasibility study | historical; superseded where the design document says so |
| `design.md` | Python → C++26 converter: design document and build plan (sections 13-15 hold the review resolutions) | authoritative on mechanism |
| `dialect-spec.md` | Python → C++26 converter: dialect specification v0.5 | authoritative on semantics |

Precedence: on semantics the dialect specification wins; on mechanism the design document
wins; the feasibility study is history.

Also here:

* `DECISIONS.md` — every decision taken, with its register entry, plus the findings the
  executable artefacts produced.
* `deviations.toml` — the deviation register as data (read by the harness and the linter).
* `reviews/round-{1,2,3}.md` — the external reviews, verbatim. Each finding's resolution is in
  the design document (sections 13-15) and in the revision log of the spec (section 13).
* `drafts/object.hpp.draft` — the v4 object-model header from the design document, kept as a
  draft (it does not compile standalone); the reference model under `refmodel/` is the
  executable statement of the same design and is what the real header is written from.
