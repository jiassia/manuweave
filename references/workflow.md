# JSON-driven local workflow

The host agent interprets the request, maps semantic roles, assesses evidence, and inspects pages. `SKILL.md` routes to the required static fragment; local scripts execute deterministic operations. No separate AI service or framework is required.

## Resolve and apply rules

Identify the source manuscript, profile or supplied reference, manuscript type/stage, and a new output path. Formatting-only is the default. Inspect native content and objects before planning changes. A reference contributes extracted rules, not manuscript text or template source files.

Read the profile's `rules`, `page`, and `extracted_format`. They retain detailed typography, paragraph behavior, elements, page geometry, and conditions. Match titles, authors, affiliations, abstracts, keywords, heading levels, body, mathematics, figures, tables, captions, references, and running matter individually. Preserve bilingual roles, inline exceptions, units, and section transitions.

Use explicit fonts, sizes, alignment, indents, paragraph spacing, multiple/exact/minimum line spacing, paper dimensions, margins, columns, and column gaps. Source URLs, versions, hashes, and locators record provenance. Original class/style/bibliography files, archives, PDFs, and Word templates are neither packaged nor acquired as runtime dependencies. A class name or option list is not formatting data.

Validate role maps and edit plans through the supplied schemas and operation whitelist. Apply changes to a copy and compare protected content and native objects. Preserve formulas, media, merged tables, fields, notes, and citations. Do not reconstruct the manuscript from Markdown or execute arbitrary generated code.

## Tools

Run `python scripts/manuweave.py` from the installed Skill, or use an absolute script path. Its Python dependencies come from `requirements.txt`; uv is optional. Commands return JSON for host orchestration.

| Command | Purpose |
| --- | --- |
| `doctor` | Identify existing Python dependencies, renderers, TeX tools, and fonts. |
| `presets list/show/catalog` | Read extracted rule profiles and provenance. |
| `presets verify NAME` | Validate a profile's schema and source-linked requirements. |
| `presets export/import` | Save or load custom JSON requirements. |
| `learn-style SOURCE --output PROFILE` | Extract effective formatting into a reusable JSON profile. |
| `inspect SOURCE` | Return native blocks, roles, and object locations. |
| `analyze-missing SOURCE` | Identify structural tasks and evidence needs. |
| `plan SOURCE --preset NAME --output PLAN` | Build a controlled plan; a supplied reference can replace the preset. |
| `apply PLAN --output FILE` | Execute supported operations on a copy. |
| `audit BEFORE AFTER --profile PROFILE` | Compare protected content and format requirements. |
| `render SOURCE --output DIR` | Render with an existing local tool. |
| `repair PLAN --output FILE` | Apply corrected rules with bounded rechecks. |
| `complete SOURCE --request REQUEST --output DOCX` | Add authorized structure and evidence-linked content. |
| `refresh-fields SOURCE --output DOCX` | Refresh supported TOC caches from real Word layout. |
| `run SOURCE --preset NAME --output DIR` | Coordinate parsing, rule application, checks, and available rendering. |
| `resume STATE` | Resume a saved local operation after identity checks. |
| `convert SOURCE --output FILE` | Explicit optional conversion with a loss report. |
| `schema --output DIR` | Export the supported interchange contracts. |

The host performs these operations; ordinary use requires only a natural-language request and files. Querying a profile does not modify a document.

## Render and finish

Use installed Word or LibreOffice for DOCX, and installed TeX tools for LaTeX. The LaTeX engine generates controlled formatting settings from JSON without loading an original publisher template package. Compile with fixed no-shell-escape options, bounded processes, and path/security preflight. Keep the original and a change record.

Use the local font inventory. Missing required fonts become concrete issues; a user-selected installed substitute records its deviation. Do not download fonts or install system tools as part of ordinary formatting. Inspect actual fonts and each rendered page, then repair specific defects and recheck affected objects. A check that did not occur stays `UNVERIFIED`.

`run` infers roles. When inspection identifies ambiguous authors, affiliations or bilingual blocks, use `plan SOURCE --preset NAME --roles ROLES --output PLAN`, then `apply PLAN --output FILE`, `audit SOURCE FILE --profile PROFILE --roles ROLES` and `render FILE --profile PROFILE --roles ROLES --output PREVIEW`. Retain the same role map across these checks. The roles JSON is `{"roles":{"p0":"title","p1":"author"}}`, using IDs from that source. A reference plan uses `--reference REFERENCE` in place of `--preset`. Export or save the resolved profile as PROFILE. LaTeX role overrides are currently rejected.

For a coordinated academic run, inspect every rendered page, fill the exported `VisualReview` contract with specific observations and the saved page hashes, then call `accept STATE --review REVIEW`. Official runs use `official accept DIRECTORY --review REVIEW`. Acceptance preserves failed and unperformed checks. Automatic font checks sample body glyphs only; other roles and full glyph coverage require review. Blank space on a short last page alone does not authorize changing explicit page or spacing requirements.

`resume STATE` verifies the source, native output, saved JSON, PDF and page images before reusing results. Interrupted runs can resume from saved stages; completed runs return their saved result, including failures. After resolving a completed rendering failure, start a new run directory. Legacy results without a recorded PDF identity need a new run. Changed inputs require a new plan; changed artifacts must not be adopted as valid recovery output. Official runs have no resume command: inspect retained files and rerun into a new directory after resolving a failure.

Safe structure may be completed automatically. Substantive additions require explicit authorization and matching source evidence. Extractive matching verifies provenance; other generated text remains for review. Research data, references, author identity, affiliations, funding, and ethics information require real materials. Deliver the editable result, concise audit, and necessary previews.
