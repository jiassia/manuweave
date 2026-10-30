# ManuWeave JSON rule registry

The registry loads extracted rule profiles from `src/manuweave/data/templates/**/profiles/*.json` and authored layouts from `src/manuweave/data/presets/`. The [homepage list](../README.md#built-in-templates) identifies the installed profiles.

Built-ins contain JSON requirements, not original template files. `rules` holds role-based typography and paragraph properties; `page` holds paper and page geometry; `extracted_format` retains detailed element properties and conditions. Title, author, affiliation, abstract, keyword, heading, body, mathematics, figure, table, caption, reference, running-matter, column, and column-gap requirements remain separate.

Source URLs, versions, hashes, and locators establish provenance. The registry does not bundle or download original template classes, styles, bibliography styles, documents, archives, or PDFs. Class names, option lists, and source-file dependencies do not substitute for extracted numeric or semantic formatting requirements.

`load_preset` resolves a profile ID, alias, natural-language selection, or JSON path. Duplicate IDs fail validation. Ambiguous names return candidates. The installed registry resolves independently of the working directory.

Custom JSON profiles use the same validated contract. Export to a new file, assign a distinct name/ID/version and explicit rules, then import into a local library. `presets list/show/catalog` exposes the data; `presets verify` validates it. Detailed operations appear in the [workflow](../references/workflow.md).
