# string-census

**English** · [简体中文](README.zh-CN.md)

An agent skill that audits every interface string your product ships, in every locale, and tells you whether the words are ready to release.

Placeholders that do not match, plurals with no `other` branch, sentences glued together in code, "Yes / No" dialogs, "Click here" links, errors with no way forward, glossary drift, untranslated and overflowing text: string census finds them across all your catalogs at once and sorts them into one ledger with a verdict.

## Why

Interface copy is reviewed one screen at a time and translated one key at a time. Nobody reads the catalogs as a whole, so the problems that only show up across files (a placeholder renamed in one language, a term that changed halfway through a flow, a button that is fine in English and three times too long in German) reach users first. String census reads them as a whole.

## Features

- **Three tiers, one verdict.** `BREAKS` (will crash or show wrong data), `MISLEADS` (sends people the wrong way), `DRIFTS` (inconsistency and translation debt). Verdict `HOLD`, `SHIP WITH DEBT`, `CLEAN WITH DRIFT` or `CLEAN`, with matching exit codes for CI.
- **Census card.** A small JSON file frozen before the run: source locale, glossary, capitalisation policy per element type, slot widths, role overrides, allowed identical strings.
- **Placeholder checks** for ICU `{name}`, ICU plural/select, mustache `{{name}}`, printf `%s` `%1$s` `%@`, Ruby `%{name}`, and optional Laravel `:name`.
- **ICU structure checks:** unbalanced braces, plural or select with no `other`.
- **Cross-locale checks:** missing keys, orphan keys, empty translations, untranslated strings, one source string translated two ways, text over its slot or past a growth factor (CJK counted double width).
- **Wording checks on the source:** vague links, "Are you sure", Yes/No/OK buttons, "Oops" errors, errors with no next step, negative toggles, "successfully", "Please" in controls, instruction placeholders, fake `(s)` plurals, glossary terms, case policy.
- **Code scan:** sentences concatenated around a variable, `=== 1 ? "" : "s"` plural hacks, dates formatted without a locale, `aria-label`s that name a glyph.
- **Reads** JSON (nested, i18next, next-intl, vue-i18n), Flutter ARB, and Apple `.strings`. Python 3 standard library only.

## Install

The skill is the folder. Copy or clone it where your agent looks for skills.

**Claude Code**

```bash
git clone https://github.com/fangdididi/string-census ~/.claude/skills/string-census
```

**Codex**

```bash
git clone https://github.com/fangdididi/string-census ~/.codex/skills/string-census
```

**Cursor**: clone into your project's `.cursor/skills/string-census` (or your global skills folder) and mention "string census" in chat.

**Any other agent**: point it at `SKILL.md` (or `SKILL.zh-CN.md`) and keep `scripts/census.py` next to it.

## Usage

Ask your agent:

> Run a string census on `web/locales` before we ship the German launch. Source is English.

Or run the checker yourself:

```bash
python3 scripts/census.py locales/*.json --source en --card census-card.json --code src > census-ledger.md
echo $?   # 2 HOLD · 1 SHIP WITH DEBT · 0 CLEAN
```

Options: `--format json`, `--colon` (treat `:name` as a placeholder), repeat `--code` for several directories.

## Example

```bash
cd examples/demo-app
python3 ../../scripts/census.py locales/en.json locales/de.json locales/zh-CN.json --source en --card census-card.json --code src
```

```text
# String census: HOLD

| Tier | Count |
| --- | --- |
| BREAKS | 7 |
| MISLEADS | 7 |
| DRIFTS | 11 |
```

Some of what it finds:

| Tier | Rule | Locale | Where | Text |
| --- | --- | --- | --- | --- |
| BREAKS | placeholder-mismatch | de | `project.owner_label` | `Gehört {owner}` (source has `{name}`) |
| BREAKS | icu-syntax | de | `project.count` | plural with no `other` |
| BREAKS | empty-translation | zh-CN | `settings.email_placeholder` | empty |
| BREAKS | plural-hack | code | `ProjectHeader.tsx:3` | `files.length === 1 ? "" : "s"` |
| MISLEADS | are-you-sure | en | `project.delete_confirm` | `Are you sure?` |
| MISLEADS | glyph-name | code | `ProjectHeader.tsx:8` | `aria-label="Trash icon"` |
| DRIFTS | over-slot | de | `project.delete_button` | 44 columns in a 24-column button |

Full ledger: [examples/demo-app/expected-ledger.md](examples/demo-app/expected-ledger.md).

## File structure

```text
string-census/
├── SKILL.md                  # the skill (English)
├── SKILL.zh-CN.md            # the skill (Chinese)
├── README.md
├── README.zh-CN.md
├── LICENSE
├── scripts/
│   └── census.py             # the checker (stdlib only)
├── tests/
│   └── test_census.py        # 76 tests: python3 -m unittest discover -s tests
└── examples/
    └── demo-app/
        ├── census-card.json
        ├── locales/          # en, de, zh-CN with planted problems
        ├── src/ProjectHeader.tsx
        └── expected-ledger.md
```

## Limits

- Rule checks on wording run on the source locale (English rules). Other languages get the structural and cross-locale checks; their wording still needs a fluent reader.
- `no-way-forward` and role detection are heuristics. The skill tells the agent to read each finding in context before acting.
- Strings from a server, CMS or remote config are reported as not covered unless you export them.

## License

MIT © fangdididi
