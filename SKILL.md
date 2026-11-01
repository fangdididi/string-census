---
name: string-census
description: Audit every interface string a product ships, across every locale, before a release or a new language goes live. Inventories the catalogs, freezes a census card (source locale, glossary, case policy, slot widths), runs a checker for broken placeholders, bad plurals, missing or orphan keys, untranslated and overflowing text, and misleading wording, then sorts findings into BREAKS / MISLEADS / DRIFTS with a HOLD, SHIP WITH DEBT or CLEAN verdict. Use for "check our translations", "audit the copy in our locale files", "are we ready to launch in German/Japanese", or before merging a big string change.
---

# String census

## What this is

A product's words live in catalogs: `en.json`, `app_de.arb`, `fr.lproj/Localizable.strings`, plus a few sentences glued together in code. Nobody reads those files as a whole. Each screen gets reviewed on its own, each translator sees one key at a time, and the damage shows up after release: a German button that says `{count} Datei(en)`, a Japanese toast that crashes because `{name}` became `{名前}`, a "Yes / No" dialog that nobody can answer without reading the body, and the same object called "workspace" in one menu and "folder" in the next.

String census treats the catalogs as one body of text and audits it the way a census counts a population: every string, every locale, one ledger. It answers three questions in order:

1. **Will anything break?** Placeholders that do not match the source, ICU messages without an `other` branch, unbalanced braces, empty translations, fake plurals, sentences glued around a variable in code.
2. **Will anything send people the wrong way?** Errors with no way forward, "Are you sure?" dialogs, Yes/No buttons, "Click here" links, accessible names that describe a glyph instead of an action.
3. **Where is the drift?** Terms that leave the glossary, mixed capitalisation, untranslated strings, missing and orphan keys, text that will not fit its slot, one source string translated two ways.

It does not rewrite your product's voice. A deliberate brand voice is not a finding; inconsistency, ambiguity and breakage are.

## When to use it

- Before a release that adds or changes many strings.
- Before turning on a new language, or after a batch of translations comes back from a vendor or a model.
- When users report "weird text", raw keys, or crashes on one locale only.
- When adopting a glossary or capitalisation policy and you want to know how far the current copy is from it.

Not for: writing marketing pages, reviewing one screen's visual design, or legal text review.

## What you need

- The catalog files (JSON, ARB, or Apple `.strings`; for other formats, export to JSON first).
- Which locale is the source of truth.
- Optional but valuable: the code directory, so glued sentences and plural hacks are caught.
- Optional: a glossary, a capitalisation policy, and slot widths for tight places (buttons, tabs, table headers).

## Steps

### 1. Find every place words live

Search the repo for the translation call (`t(`, `i18n.t`, `$t(`, `<FormattedMessage`, `NSLocalizedString`, `AppLocalizations.of`, `getString(`) and follow it to the files it reads. Also look for strings that come from a CMS, the server, or remote config, and write them down as **not covered**. A census that silently skips server strings is lying about coverage.

### 2. Freeze the census card

Write `census-card.json` before you run anything, so the rules do not bend to fit the results:

```json
{
  "product": "Acme Tasks web app",
  "source": "en",
  "glossary": { "workspace": ["folder", "space"], "sign in": ["log in", "login"] },
  "case_policy": { "button": "sentence", "title": "sentence", "label": "sentence" },
  "slots": { "button": 24, "tabs.inbox_title": 12 },
  "growth": { "button": 1.6 },
  "roles": { "^cta\\.": "button" },
  "same_in_all_locales": ["OK", "Wi-Fi"],
  "ignore_keys": ["debug.build_id"],
  "next_step_words": ["reconnect"]
}
```

- `glossary` maps the preferred term to the words that must not stand in for it.
- `case_policy` is per role: `sentence` or `title`. If the project has none, sentence case is the safe default; record that you chose it.
- `slots` are column budgets (CJK characters count as two). A key-specific slot wins over a role slot. Without a slot, the checker flags a translation that grows past the role's growth factor.
- `roles` are regex overrides when key names do not reveal what a string is. Otherwise roles come from key names: `_button`, `_error`, `_toggle`, `_placeholder`, `_link`, `_title`, `_label`, `_toast`, `_empty`, `_confirm`.

### 3. Run the census

```bash
python3 scripts/census.py locales/*.json --source en --card census-card.json --code src > census-ledger.md
echo $?   # 2 = HOLD, 1 = SHIP WITH DEBT, 0 = CLEAN / CLEAN WITH DRIFT
```

Use `--format json` to feed another tool, and `--colon` if the project uses `:name` placeholders.

### 4. Read the ledger, do not just count it

The script is a net, not a judge. For each finding:

- **BREAKS**: confirm, then fix. These are never "won't fix". A placeholder mismatch in one locale is a crash or a wrong name on screen for every user of that language.
- **MISLEADS**: read the string in its screen. `no-way-forward` is a heuristic (no recovery verb found); an error like "This link has expired. Ask the sender for a new one." passes once you add `ask` to `next_step_words`, but "Invalid input." does not.
- **DRIFTS**: batch them. One glossary fix in the source usually clears a dozen rows.

Then read the source catalog yourself for what no regex sees: a button that does not start with a verb, a confirmation that does not name the object, an empty state with no next action, a toggle whose ON state is unclear.

### 5. Fix in the right order

1. Fix the **source** message first (structure, placeholders, plural form, wording).
2. Mark every translation of a changed source key as **stale** and send it back for re-translation. Do not hand-patch other languages you cannot read; a "fixed" placeholder in a sentence you do not understand is a new bug.
3. Fix code: replace glued sentences with one message plus placeholders, replace `n === 1 ? "" : "s"` with ICU plurals or `Intl.PluralRules`, pass a locale to date and number formatting, and give icon buttons an action name.

### 6. Re-run and close the ledger

Re-run with the same card. Report the verdict, counts per tier before and after, what was not covered (server/CMS strings, formats you did not export), and every finding you accepted as debt with a reason.

## Reading the verdicts

| Verdict | Meaning | Ship? |
| --- | --- | --- |
| HOLD | At least one BREAKS finding | No |
| SHIP WITH DEBT | No breaks, at least one MISLEADS | Only with a named owner and date for each |
| CLEAN WITH DRIFT | Only DRIFTS | Yes; schedule the drift |
| CLEAN | Nothing found in what was covered | Yes; state the coverage |

## Rules of thumb behind the checks

- **One message per sentence.** Word order changes by language, so `"You have " + n + " files"` cannot be translated. Write `You have {n, plural, one {# file} other {# files}}`.
- **Every plural and select has `other`.** Many languages have more than two plural forms; `other` is the one that always exists.
- **Errors are instructions.** Say what failed and what to do: "Unable to save. Check your connection and try again." No "Oops", no blame, no exclamation marks.
- **Dialogs answer themselves.** Title names action and object ("Delete 'Q3 report'?"); buttons are verb plus object ("Delete report" / "Cancel"), never Yes/No.
- **Links name the destination.** "Read the billing guide", not "Click here".
- **Toggles describe the ON state.** "Send read receipts", not "Don't send read receipts".
- **Placeholders show an example**, `name@example.com`, not an instruction.
- **One term per thing, one case per element type.**
- **Leave room.** German and Finnish often run 30-60% longer than English; short labels can double.

## Example

`examples/demo-app` holds a three-locale task app with planted problems. Running the command in step 3 there gives `HOLD` with seven breaks, including:

| Tier | Rule | Locale | Key | Text |
| --- | --- | --- | --- | --- |
| BREAKS | placeholder-mismatch | de | `project.owner_label` | `Gehört {owner}` (source uses `{name}`) |
| BREAKS | icu-syntax | de | `project.count` | plural with no `other` branch |
| BREAKS | concatenated-sentence | code | `ProjectHeader.tsx:2` | `"You have " + files.length + " new files"` |
| MISLEADS | yes-no-button | en | `project.delete_confirm_yes_button` | `Yes` |
| DRIFTS | term-drift | en | `billing.seats_label` | "folder" where the glossary says "workspace" |

The full output is in `examples/demo-app/expected-ledger.md`.

## Tips

- Run it in CI on pull requests that touch catalogs; fail on exit code 2.
- Keep the card in the repo; change it in its own commit, never in the same commit as the fixes.
- A string identical to the source is not always untranslated (brand names, "OK"); add those to `same_in_all_locales` instead of ignoring the rule.
- Long German or Finnish text is not a translator error. Fix the slot (wrap, truncate with a tooltip, or shorten the source) rather than asking for an unnatural translation.
- When the same source text needs two translations because the contexts differ, split it into two keys with descriptions, not one key.
