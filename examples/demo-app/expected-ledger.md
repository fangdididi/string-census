# String census: HOLD

19 source strings, locales: de, en, zh-CN

| Tier | Count |
| --- | --- |
| BREAKS | 7 |
| MISLEADS | 7 |
| DRIFTS | 11 |

## BREAKS

| Rule | Locale | Key / location | Text | Why |
| --- | --- | --- | --- | --- |
| concatenated-sentence |  | `src/ProjectHeader.tsx:2` | const subtitle = "You have " + files.length + " new files"; | Sentence glued around a variable; word order differs per language. Use one message with a placeholder. |
| empty-translation | zh-CN | `settings.email_placeholder` |  | Empty string renders as a blank control. |
| fake-plural | de | `project.files_label` | {count} Datei(en) | Inherited fake plural; fix the source message first, then re-translate. |
| fake-plural | en | `project.files_label` | {count} file(s) | '(s)' fakes a plural; use the locale's plural rules (ICU plural with 'other'). |
| icu-syntax | de | `project.count` | {count, plural, one {# Projekt}} | plural 'count' has no 'other' branch |
| placeholder-mismatch | de | `project.owner_label` | Gehört {owner} | missing {name}; unknown {owner} |
| plural-hack |  | `src/ProjectHeader.tsx:3` | const noun = files.length === 1 ? "" : "s"; | Two-form plural hack; many languages have more forms. Use ICU plural or Intl.PluralRules. |

## MISLEADS

| Rule | Locale | Key / location | Text | Why |
| --- | --- | --- | --- | --- |
| are-you-sure | en | `project.delete_confirm` | Are you sure? | Name the action and the object instead, e.g. "Delete 'Q3 report'?". |
| glyph-name |  | `src/ProjectHeader.tsx:8` | <button aria-label="Trash icon" onClick={onDelete}>🗑</button> | Accessible name describes the glyph; name the action ('Close dialog', 'Delete project'). |
| no-way-forward | en | `errors.name_error` | That name is too short. | Error names no next step (heuristic: no recovery verb found). Confirm by reading it. |
| no-way-forward | en | `errors.save_error` | Oops! Something went wrong. | Error names no next step (heuristic: no recovery verb found). Confirm by reading it. |
| shrug-error | en | `errors.save_error` | Oops! Something went wrong. | Say what failed and what to do next, without blame or playfulness. |
| vague-link | en | `project.share_link` | Click here | Link text must name its destination; screen-reader link lists read it alone. |
| yes-no-button | en | `project.delete_confirm_yes_button` | Yes | A button answers the dialog on its own: verb plus object, e.g. 'Delete project'. |

## DRIFTS

| Rule | Locale | Key / location | Text | Why |
| --- | --- | --- | --- | --- |
| case-policy | en | `nav.projects_title` | Your Projects | Case policy for title is sentence case; this reads as title case. |
| error-exclamation | en | `errors.save_error` | Oops! Something went wrong. | No exclamation marks in errors. |
| instruction-placeholder | en | `settings.email_placeholder` | Enter your email | A placeholder shows an example value (name@example.com), not an instruction; it vanishes on typing. |
| missing-key | de | `settings.email_placeholder` |  | No translation; the app will fall back or show the raw key. |
| negative-toggle | en | `settings.receipts_toggle` | Don't send read receipts | Label a toggle for its ON state; a negative label becomes a double negative. |
| orphan-key | de | `legacy.old_banner` | Alte Version | Key exists only in this locale; dead or never added to the source. |
| over-slot | de | `project.delete_button` | Projekt dauerhaft und unwiderruflich löschen | 44 columns > slot of 24. |
| successfully | en | `project.archived_toast` | Project archived successfully | Cut 'successfully': 'Changes saved' already says it worked. |
| term-drift | en | `billing.seats_label` | Seats in your folder | Glossary says 'workspace', not 'folder'. |
| unlocalized-date |  | `src/ProjectHeader.tsx:7` | <p>{subtitle} · {new Date(project.updated).toLocaleDateString()}</p> | Date/number formatted without a locale; pass the user's locale (Intl.DateTimeFormat). |
| untranslated | de | `errors.upload_error` | Upload failed. Check your connection and try again. | Identical to the source text. |

