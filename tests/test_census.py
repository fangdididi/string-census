import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import census as C  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "census.py")
DEMO = os.path.join(ROOT, "examples", "demo-app")


def rules(res, locale=None, rule=None):
    out = []
    for f in res["findings"]:
        if locale and f.get("locale") != locale:
            continue
        if rule and f["rule"] != rule:
            continue
        out.append(f)
    return out


def run(src, tgt=None, card=None):
    cats = {"en": src}
    if tgt is not None:
        cats["fr"] = tgt
    return C.census(cats, "en", card or {})


class Loading(unittest.TestCase):
    def test_flatten_nested(self):
        self.assertEqual(C.flatten({"a": {"b": "x", "c": {"d": "y"}}}), {"a.b": "x", "a.c.d": "y"})

    def test_flatten_skips_arb_metadata(self):
        self.assertEqual(C.flatten({"hi": "Hi", "@hi": {"description": "greeting"}}), {"hi": "Hi"})

    def test_flatten_lists(self):
        self.assertEqual(C.flatten({"tips": ["a", "b"]}), {"tips[0]": "a", "tips[1]": "b"})

    def test_apple_strings(self):
        txt = '/* comment */\n"save.button" = "Save";\n"quote" = "Say \\"hi\\"";\n'
        self.assertEqual(C.parse_apple_strings(txt), {"save.button": "Save", "quote": 'Say "hi"'})

    def test_locale_from_json_name(self):
        self.assertEqual(C.locale_from_path("/x/locales/de.json"), "de")

    def test_locale_from_arb_prefix(self):
        self.assertEqual(C.locale_from_path("lib/l10n/app_ja.arb"), "ja")

    def test_locale_from_lproj(self):
        self.assertEqual(C.locale_from_path("App/fr.lproj/Localizable.strings"), "fr")

    def test_locale_from_i18next_folder(self):
        self.assertEqual(C.locale_from_path("public/locales/pt-BR/translation.json"), "pt-BR")


class Placeholders(unittest.TestCase):
    def test_icu_simple(self):
        self.assertEqual(C.placeholders("Hi {name}"), {"{name}"})

    def test_icu_plural_argument(self):
        self.assertEqual(C.placeholders("{n, plural, one {# file} other {# files}}"), {"{n}"})

    def test_mustache(self):
        self.assertEqual(C.placeholders("Hi {{ user }}"), {"{user}"})

    def test_printf(self):
        self.assertEqual(C.placeholders("%s has %d items"), {"%s", "%d"})

    def test_printf_positional(self):
        self.assertEqual(C.placeholders("%2$s by %1$s"), {"%2$s", "%1$s"})

    def test_printf_long(self):
        self.assertEqual(C.placeholders("%ld items"), {"%d"})

    def test_ios_object(self):
        self.assertEqual(C.placeholders("Hello %@"), {"%@"})

    def test_percent_literal_ignored(self):
        self.assertEqual(C.placeholders("100%% done"), set())

    def test_ruby_style(self):
        self.assertEqual(C.placeholders("Hi %{name}"), {"%{name}"})

    def test_colon_opt_in(self):
        self.assertEqual(C.placeholders("Hi :name"), set())
        self.assertEqual(C.placeholders("Hi :name", colon=True), {":name"})

    def test_quoted_brace_not_placeholder(self):
        self.assertEqual(C.placeholders("Use '{' to open"), set())


class Icu(unittest.TestCase):
    def test_balanced_ok(self):
        self.assertEqual(C.icu_problems("{n, plural, one {# a} other {# b}}"), [])

    def test_unbalanced_open(self):
        self.assertIn("unbalanced braces", C.icu_problems("Hi {name"))

    def test_unbalanced_close(self):
        self.assertIn("unbalanced braces", C.icu_problems("Hi name}"))

    def test_plural_without_other(self):
        self.assertTrue(C.icu_problems("{n, plural, one {# a}}"))

    def test_select_without_other(self):
        self.assertTrue(C.icu_problems("{g, select, male {He} female {She}}"))

    def test_exact_match_branch(self):
        self.assertEqual(C.icu_problems("{n, plural, =0 {None} other {#}}"), [])


class Roles(unittest.TestCase):
    def test_button_suffix(self):
        self.assertEqual(C.role_of("project.delete_button"), "button")

    def test_error_segment(self):
        self.assertEqual(C.role_of("errors.network.save_error"), "error")

    def test_toggle(self):
        self.assertEqual(C.role_of("settings.receipts_toggle"), "toggle")

    def test_camel_case_suffix(self):
        self.assertEqual(C.role_of("project.deleteButton"), "button")

    def test_parent_segment(self):
        self.assertEqual(C.role_of("errors.network"), "error")

    def test_default_text(self):
        self.assertEqual(C.role_of("marketing.tagline"), "text")

    def test_override(self):
        self.assertEqual(C.role_of("cta.go", {r"^cta\.": "link"}), "link")


class Wording(unittest.TestCase):
    def test_click_here(self):
        self.assertTrue(rules(run({"a.share_link": "Click here"}), rule="vague-link"))

    def test_are_you_sure(self):
        self.assertTrue(rules(run({"d.confirm": "Are you sure?"}), rule="are-you-sure"))

    def test_yes_button(self):
        self.assertTrue(rules(run({"d.ok_button": "OK"}), rule="yes-no-button"))

    def test_verb_button_clean(self):
        self.assertEqual(run({"d.delete_button": "Delete project"})["findings"], [])

    def test_shrug_error(self):
        self.assertTrue(rules(run({"e.save_error": "Oops, something went wrong"}), rule="shrug-error"))

    def test_error_with_next_step_passes(self):
        res = run({"e.save_error": "Unable to save. Check your connection and try again."})
        self.assertEqual(res["findings"], [])

    def test_error_without_next_step(self):
        self.assertTrue(rules(run({"e.name_error": "Name too short."}), rule="no-way-forward"))

    def test_card_next_step_words(self):
        res = run({"e.name_error": "Name too short. Lengthen it."}, card={"next_step_words": ["lengthen"]})
        self.assertFalse(rules(res, rule="no-way-forward"))

    def test_negative_toggle(self):
        self.assertTrue(rules(run({"s.x_toggle": "Hide previews"}), rule="negative-toggle"))

    def test_successfully(self):
        self.assertTrue(rules(run({"t.saved_toast": "Saved successfully"}), rule="successfully"))

    def test_fake_plural_source(self):
        self.assertEqual(rules(run({"f.count_label": "{n} file(s)"}), rule="fake-plural")[0]["tier"], "BREAKS")

    def test_instruction_placeholder(self):
        self.assertTrue(rules(run({"f.email_placeholder": "Enter your email"}), rule="instruction-placeholder"))

    def test_glossary(self):
        res = run({"b.seats_label": "Seats in this folder"}, card={"glossary": {"workspace": ["folder"]}})
        self.assertTrue(rules(res, rule="term-drift"))

    def test_glossary_word_boundary(self):
        res = run({"b.x_label": "Spaceship parts"}, card={"glossary": {"workspace": ["space"]}})
        self.assertFalse(rules(res, rule="term-drift"))

    def test_case_policy(self):
        res = run({"n.main_title": "Your Projects"}, card={"case_policy": {"title": "sentence"}})
        self.assertTrue(rules(res, rule="case-policy"))

    def test_case_style(self):
        self.assertEqual(C.case_style("Save Changes"), "title")
        self.assertEqual(C.case_style("Save changes"), "sentence")
        self.assertIsNone(C.case_style("Save"))


class CrossLocale(unittest.TestCase):
    def test_missing_key(self):
        self.assertTrue(rules(run({"a": "Hello there"}, {}), rule="missing-key"))

    def test_orphan_key(self):
        self.assertTrue(rules(run({}, {"old": "Vieux"}), rule="orphan-key"))

    def test_empty_translation_breaks(self):
        f = rules(run({"a": "Hello there"}, {"a": " "}), rule="empty-translation")
        self.assertEqual(f[0]["tier"], "BREAKS")

    def test_placeholder_mismatch(self):
        f = rules(run({"a": "Owned by {name}"}, {"a": "Possédé par {owner}"}), rule="placeholder-mismatch")
        self.assertIn("missing {name}", f[0]["why"])
        self.assertIn("unknown {owner}", f[0]["why"])

    def test_placeholder_reordered_ok(self):
        res = run({"a": "{a} and {b}"}, {"a": "{b} et {a}"})
        self.assertFalse(rules(res, rule="placeholder-mismatch"))

    def test_untranslated(self):
        self.assertTrue(rules(run({"a": "Upload failed"}, {"a": "Upload failed"}), rule="untranslated"))

    def test_untranslated_allowlist(self):
        res = run({"a": "Open Source"}, {"a": "Open Source"}, card={"same_in_all_locales": ["open source"]})
        self.assertFalse(rules(res, rule="untranslated"))

    def test_single_word_same_ok(self):
        self.assertFalse(rules(run({"a": "Email"}, {"a": "Email"}), rule="untranslated"))

    def test_target_icu_problem(self):
        self.assertTrue(rules(run({"a": "{n, plural, one {#} other {#}}"}, {"a": "{n, plural, one {#}}"}), locale="fr", rule="icu-syntax"))

    def test_slot_limit(self):
        res = run({"a.go_button": "Delete"}, {"a.go_button": "Supprimer définitivement"}, card={"slots": {"button": 12}})
        self.assertTrue(rules(res, locale="fr", rule="over-slot"))

    def test_growth_without_slot(self):
        res = run({"a.go_button": "Delete"}, {"a.go_button": "Supprimer définitivement maintenant"})
        self.assertTrue(rules(res, rule="growth"))

    def test_cjk_counts_double(self):
        self.assertEqual(C.visible_len("删除"), 4)

    def test_split_translation(self):
        res = run({"a": "Save changes", "b": "Save changes"}, {"a": "Enregistrer", "b": "Sauvegarder"})
        self.assertTrue(rules(res, rule="split-translation"))

    def test_ignore_keys(self):
        res = run({"a": "Click here"}, {}, card={"ignore_keys": ["a"]})
        self.assertEqual(res["findings"], [])

    def test_unknown_source_raises(self):
        with self.assertRaises(ValueError):
            C.census({"en": {}}, "de")


class Verdicts(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(run({"a.save_button": "Save"}, {"a.save_button": "Enregistrer"})["verdict"], "CLEAN")

    def test_hold_on_breaks(self):
        self.assertEqual(run({"a": "Hi {name}"}, {"a": "Salut"})["verdict"], "HOLD")

    def test_debt_on_misleads(self):
        self.assertEqual(run({"a.ok_button": "OK"})["verdict"], "SHIP WITH DEBT")

    def test_drift_only(self):
        self.assertEqual(run({"t.x_toast": "Saved successfully"})["verdict"], "CLEAN WITH DRIFT")

    def test_sorted_by_tier(self):
        res = run({"a.ok_button": "OK", "b": "Hi {n}", "t.x_toast": "Done successfully"}, {"a.ok_button": "OK", "b": "Salut", "t.x_toast": "Fait"})
        tiers = [f["tier"] for f in res["findings"]]
        self.assertEqual(tiers, sorted(tiers, key=C.TIERS.index))


class CodeScan(unittest.TestCase):
    def scan(self, line):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.tsx")
            open(p, "w").write(line + "\n")
            return [f["rule"] for f in C.scan_code(d)]

    def test_concatenation(self):
        self.assertIn("concatenated-sentence", self.scan('const s = "You have " + n + " new files";'))

    def test_plural_hack(self):
        self.assertIn("plural-hack", self.scan('const s = n === 1 ? "" : "s";'))

    def test_unlocalized_date(self):
        self.assertIn("unlocalized-date", self.scan("d.toLocaleDateString()"))

    def test_localized_date_ok(self):
        self.assertEqual(self.scan("d.toLocaleDateString(locale)"), [])

    def test_glyph_aria(self):
        self.assertIn("glyph-name", self.scan('<button aria-label="Close icon">x</button>'))

    def test_skips_node_modules(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "node_modules"))
            open(os.path.join(d, "node_modules", "a.js"), "w").write('x = "a " + b + " c"\n')
            self.assertEqual(C.scan_code(d), [])


class Cli(unittest.TestCase):
    def test_demo_exit_code_and_ledger(self):
        loc = os.path.join(DEMO, "locales")
        p = subprocess.run([sys.executable, SCRIPT, os.path.join(loc, "en.json"), os.path.join(loc, "de.json"),
                            os.path.join(loc, "zh-CN.json"), "--source", "en", "--card", os.path.join(DEMO, "census-card.json"),
                            "--code", os.path.join(DEMO, "src"), "--format", "json"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        res = json.loads(p.stdout)
        self.assertEqual(res["verdict"], "HOLD")
        got = {f["rule"] for f in res["findings"]}
        for r in ("placeholder-mismatch", "icu-syntax", "concatenated-sentence", "are-you-sure", "term-drift", "over-slot"):
            self.assertIn(r, got)

    def test_markdown_output(self):
        res = run({"a.ok_button": "OK"})
        md = C.to_markdown(res)
        self.assertIn("# String census: SHIP WITH DEBT", md)
        self.assertIn("| yes-no-button |", md)


if __name__ == "__main__":
    unittest.main()
