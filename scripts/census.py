#!/usr/bin/env python3
"""string-census: audit a product's interface strings across every locale.

Reads locale catalogs (JSON / ARB / Apple .strings), an optional census card,
and optional source code, then writes a findings ledger with a verdict.

Tiers
  BREAKS   - the string can crash, render garbage, or show wrong data
  MISLEADS - the string sends people the wrong way or leaves them stuck
  DRIFTS   - inconsistency, translation debt, or a string that will not fit

Exit code: 2 = HOLD (any BREAKS), 1 = SHIP WITH DEBT (any MISLEADS), 0 = CLEAN/DRIFTS only.
Standard library only.
"""
import argparse
import json
import os
import re
import sys

TIERS = ("BREAKS", "MISLEADS", "DRIFTS")

# ---------------------------------------------------------------- loading

def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("@"):  # ARB metadata
                continue
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                out.update(flatten(v, key))
            elif isinstance(v, str):
                out[key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}[{i}]"
            if isinstance(v, str):
                out[key] = v
            else:
                out.update(flatten(v, key))
    return out


_STRINGS_LINE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')


def parse_apple_strings(text):
    out = {}
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for line in text.splitlines():
        m = _STRINGS_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\n", "\n")
    return out


def load_catalog(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".strings"):
        return parse_apple_strings(text)
    return flatten(json.loads(text))


def locale_from_path(path):
    base = os.path.basename(path)
    if base.endswith(".strings"):
        parent = os.path.basename(os.path.dirname(path))
        if parent.endswith(".lproj"):
            return parent[: -len(".lproj")]
    name = os.path.splitext(base)[0]
    for pre in ("app_", "intl_", "messages_", "strings_"):
        if name.startswith(pre):
            name = name[len(pre):]
    if name in ("translation", "messages", "common", "strings"):
        name = os.path.basename(os.path.dirname(path))
    return name


# ---------------------------------------------------------------- placeholders & ICU

_PH_PATTERNS = [
    re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}"),          # {{name}}
    re.compile(r"%(\d+\$)?[-+ 0#]*\d*(?:\.\d+)?(?:l|ll|h)?[sdif@uxXc]"),  # printf / %@
    re.compile(r"%\{([A-Za-z_]\w*)\}"),                       # %{name}
    re.compile(r":([A-Za-z_]\w*)\b(?=[^:]|$)") ,                # :name (laravel) - opt-in
]


def icu_arguments(s):
    """Return list of (name, kind) for top-level ICU-style {...} arguments."""
    args, depth, i, n = [], 0, 0, len(s)
    start = None
    while i < n:
        c = s[i]
        if c == "'" and i + 1 < n and s[i + 1] in "{}'":
            i += 2
            continue
        if c == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                inner = s[start:i]
                parts = [p.strip() for p in inner.split(",", 2)]
                name = parts[0]
                kind = parts[1] if len(parts) > 1 else ""
                if name.startswith("{") and name.endswith("}"):
                    name = name[1:-1].strip()  # {{x}} handled elsewhere
                    kind = "mustache"
                args.append((name, kind, parts[2] if len(parts) > 2 else ""))
                start = None
        i += 1
    return args


def placeholders(s, colon=False):
    found = set()
    s = s.replace("%%", "")
    for m in _PH_PATTERNS[2].finditer(s):
        found.add(m.group(0))
    s = _PH_PATTERNS[2].sub("", s)
    for name, kind, _ in icu_arguments(s):
        if name and re.match(r"^[A-Za-z_][\w.]*$|^\d+$", name):
            found.add("{" + name + "}")
    for pat in _PH_PATTERNS[1:2]:
        for m in pat.finditer(s):
            tok = m.group(0)
            if tok.startswith("%") and not tok.startswith("%{"):
                tok = re.sub(r"(l|ll|h)(?=[sdif@uxXc]$)", "", tok)
                tok = re.sub(r"[-+ 0#]*\d*(?:\.\d+)?(?=[sdif@uxXc]$)", "", tok)
                if tok == "%%":
                    continue
            found.add(tok)
    if colon:
        for m in _PH_PATTERNS[3].finditer(s):
            found.add(":" + m.group(1))
    return found


def icu_problems(s):
    """Structural problems: unbalanced braces, plural/select without 'other'."""
    probs = []
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "'" and i + 1 < len(s) and s[i + 1] in "{}'":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                probs.append("unbalanced braces")
                return probs
        i += 1
    if depth != 0:
        probs.append("unbalanced braces")
        return probs
    for name, kind, body in icu_arguments(s):
        if kind in ("plural", "select", "selectordinal"):
            selectors = re.findall(r"(=?\w+)\s*\{", body)
            if "other" not in selectors:
                probs.append(f"{kind} '{name}' has no 'other' branch")
    return probs


# ---------------------------------------------------------------- roles

ROLE_HINTS = [
    ("button", ("button", "btn", "cta", "action", "submit", "cancel", "confirm_button")),
    ("error", ("error", "err", "invalid", "failed", "failure")),
    ("empty", ("empty", "no_results", "noresults", "blank")),
    ("toggle", ("toggle", "switch", "setting", "pref")),
    ("placeholder", ("placeholder", "hint")),
    ("link", ("link", "learn_more", "learnmore")),
    ("confirm", ("confirm", "dialog_title", "modal_title")),
    ("title", ("title", "heading", "header", "h1")),
    ("label", ("label", "field")),
    ("toast", ("toast", "snackbar", "success", "saved", "notice")),
]


def role_of(key, overrides=None):
    if overrides:
        for pattern, role in overrides.items():
            if re.search(pattern, key):
                return role
    raw_last = re.split(r"[./]", key)[-1]
    last = raw_last.lower()
    segs = [p.lower() for p in re.split(r"[./]", key)]
    for role, hints in ROLE_HINTS:
        for h in hints:
            if last == h or last.endswith("_" + h) or raw_last.endswith(h.capitalize()) or last.startswith(h + "_"):
                return role
    for role, hints in ROLE_HINTS:
        for h in hints:
            if any(seg in (h, h + "s") or seg.endswith("_" + h) or seg.startswith(h + "_") for seg in segs[:-1]):
                return role
    return "text"


# ---------------------------------------------------------------- source-locale wording rules

NEXT_STEP_WORDS = (
    "try", "check", "enter", "choose", "use", "contact", "sign in", "log in", "retry",
    "update", "select", "add", "remove", "refresh", "reload", "wait", "reconnect",
    "upload", "go to", "open", "restart", "verify", "allow", "turn on", "ask",
    "reset", "type", "pick", "make sure", "connect", "install", "visit",
)

SMALL_WORDS = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "at", "by", "with", "as", "but", "nor", "vs"}


def strip_placeholders(s):
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\{[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", s)
    s = re.sub(r"%(\d+\$)?[sdif@]", "", s)
    return s


def words(s):
    return re.findall(r"[A-Za-z][A-Za-z'’-]*", strip_placeholders(s))


def case_style(s):
    w = words(s)
    if len(w) < 2:
        return None
    rest = w[1:]
    caps = [x for x in rest if x.lower() not in SMALL_WORDS]
    if not caps:
        return None
    upper = sum(1 for x in caps if x[0].isupper())
    if upper == len(caps):
        return "title"
    if upper == 0:
        return "sentence"
    return "mixed"


def wording_findings(key, text, role, card):
    f = []
    low = text.lower().strip()
    stripped = strip_placeholders(text).strip()

    def add(tier, rule, msg):
        f.append({"tier": tier, "rule": rule, "key": key, "text": text, "why": msg})

    if re.search(r"\bclick here\b", low) or (role == "link" and low.strip(" .") in ("here", "this", "link", "more")):
        add("MISLEADS", "vague-link", "Link text must name its destination; screen-reader link lists read it alone.")
    if role in ("link", "text", "button") and low.strip(" .") in ("learn more", "read more", "more info"):
        add("DRIFTS", "bare-learn-more", "A bare 'Learn more' becomes ambiguous once two share a page; add what it is about.")
    if re.search(r"\bare you sure\b", low):
        add("MISLEADS", "are-you-sure", "Name the action and the object instead, e.g. \"Delete 'Q3 report'?\".")
    if role in ("button", "confirm") and low.strip(" .!") in ("yes", "no", "ok", "okay", "sure", "yep", "nope"):
        add("MISLEADS", "yes-no-button", "A button answers the dialog on its own: verb plus object, e.g. 'Delete project'.")
    if role == "error":
        if re.search(r"\b(oops|uh[- ]oh|whoops|yikes)\b", low) or "something went wrong" in low:
            add("MISLEADS", "shrug-error", "Say what failed and what to do next, without blame or playfulness.")
        if "!" in stripped:
            add("DRIFTS", "error-exclamation", "No exclamation marks in errors.")
        if not any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in NEXT_STEP_WORDS + tuple(card.get("next_step_words", []))):
            add("MISLEADS", "no-way-forward", "Error names no next step (heuristic: no recovery verb found). Confirm by reading it.")
    if role == "toggle" and re.match(r"^(don['’]t|do not|disable|hide|turn off|never)\b", low):
        add("DRIFTS", "negative-toggle", "Label a toggle for its ON state; a negative label becomes a double negative.")
    if re.search(r"\bsuccessfully\b", low):
        add("DRIFTS", "successfully", "Cut 'successfully': 'Changes saved' already says it worked.")
    if role in ("button", "label", "placeholder") and re.match(r"^please\b", low):
        add("DRIFTS", "please-in-control", "Cut 'Please' from routine controls.")
    if role == "button" and stripped.endswith("!"):
        add("DRIFTS", "button-exclamation", "Buttons name an action; no exclamation marks.")
    if FAKE_PLURAL.search(text):
        add("BREAKS", "fake-plural", "'(s)' fakes a plural; use the locale's plural rules (ICU plural with 'other').")
    if role == "placeholder" and re.match(r"^(enter|type|input|please)\b", low):
        add("DRIFTS", "instruction-placeholder", "A placeholder shows an example value (name@example.com), not an instruction; it vanishes on typing.")
    for preferred, banned in (card.get("glossary") or {}).items():
        for b in banned:
            if re.search(r"\b" + re.escape(b.lower()) + r"\b", low):
                add("DRIFTS", "term-drift", f"Glossary says '{preferred}', not '{b}'.")
    policy = (card.get("case_policy") or {}).get(role)
    if policy:
        st = case_style(text)
        if st and st != policy:
            add("DRIFTS", "case-policy", f"Case policy for {role} is {policy} case; this reads as {st} case.")
    return f


# ---------------------------------------------------------------- cross-locale checks

FAKE_PLURAL = re.compile(r"[A-Za-z\u00C0-\u024F]\((?:s|es|en|e|n|er|ies)\)")

DEFAULT_GROWTH = {"button": 1.6, "title": 1.5, "label": 1.6, "toast": 1.5, "error": 1.4, "text": 1.4}


def visible_len(s):
    s = strip_placeholders(s)
    n = 0
    for ch in s:
        o = ord(ch)
        # East Asian wide characters count double for width budgeting
        n += 2 if (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFF60) else 1
    return n


def census(catalogs, source, card=None, colon=False):
    """catalogs: {locale: {key: text}}. Returns dict with findings + stats."""
    card = card or {}
    findings = []
    src = catalogs.get(source)
    if src is None:
        raise ValueError(f"source locale '{source}' not among catalogs: {sorted(catalogs)}")
    overrides = card.get("roles") or {}
    ignore = set(card.get("ignore_keys") or [])
    same_ok = set(w.lower() for w in (card.get("same_in_all_locales") or []))
    slots = card.get("slots") or {}
    growth = dict(DEFAULT_GROWTH)
    growth.update(card.get("growth") or {})

    def add(tier, rule, key, why, locale=None, text=None):
        f = {"tier": tier, "rule": rule, "key": key, "why": why}
        if locale:
            f["locale"] = locale
        if text is not None:
            f["text"] = text
        findings.append(f)

    roles = {}
    for key, text in src.items():
        if key in ignore:
            continue
        role = role_of(key, overrides)
        roles[key] = role
        for p in icu_problems(text):
            add("BREAKS", "icu-syntax", key, p, source, text)
        for w in wording_findings(key, text, role, card):
            w["locale"] = source
            findings.append(w)
        limit = slots.get(key) or slots.get(role)
        if isinstance(limit, int) and visible_len(text) > limit:
            add("DRIFTS", "over-slot", key, f"{visible_len(text)} columns > slot of {limit}.", source, text)

    for loc, cat in sorted(catalogs.items()):
        if loc == source:
            continue
        for key in src:
            if key in ignore:
                continue
            if key not in cat:
                add("DRIFTS", "missing-key", key, "No translation; the app will fall back or show the raw key.", loc)
                continue
            s, t = src[key], cat[key]
            if t.strip() == "" and s.strip() != "":
                add("BREAKS", "empty-translation", key, "Empty string renders as a blank control.", loc, t)
                continue
            ps, pt = placeholders(s, colon), placeholders(t, colon)
            if ps != pt:
                miss = sorted(ps - pt)
                extra = sorted(pt - ps)
                bits = []
                if miss:
                    bits.append("missing " + ", ".join(miss))
                if extra:
                    bits.append("unknown " + ", ".join(extra))
                add("BREAKS", "placeholder-mismatch", key, "; ".join(bits), loc, t)
            for p in icu_problems(t):
                add("BREAKS", "icu-syntax", key, p, loc, t)
            if FAKE_PLURAL.search(t) and not FAKE_PLURAL.search(s):
                add("BREAKS", "fake-plural", key, "Translation fakes a plural with brackets; use the locale's plural rules.", loc, t)
            elif FAKE_PLURAL.search(t):
                add("BREAKS", "fake-plural", key, "Inherited fake plural; fix the source message first, then re-translate.", loc, t)
            if (t == s and len(words(s)) >= 2 and s.lower() not in same_ok):
                add("DRIFTS", "untranslated", key, "Identical to the source text.", loc, t)
            role = roles.get(key, "text")
            limit = slots.get(key) or slots.get(role)
            if isinstance(limit, int):
                if visible_len(t) > limit:
                    add("DRIFTS", "over-slot", key, f"{visible_len(t)} columns > slot of {limit}.", loc, t)
            else:
                g = growth.get(role, 1.4)
                if visible_len(s) >= 4 and visible_len(t) > max(g * visible_len(s), visible_len(s) + 8):
                    add("DRIFTS", "growth", key, f"{visible_len(t)} vs {visible_len(s)} columns in source (> x{g}); check the slot.", loc, t)
        for key in cat:
            if key not in src and key not in ignore:
                add("DRIFTS", "orphan-key", key, "Key exists only in this locale; dead or never added to the source.", loc, cat[key])

    # same source text under different keys with different roles is fine; same object named two ways is glossary's job.
    # duplicate source text with diverging translations
    by_text = {}
    for key, text in src.items():
        by_text.setdefault(text.strip(), []).append(key)
    for text, keys in by_text.items():
        if len(keys) < 2 or len(words(text)) == 0:
            continue
        for loc, cat in sorted(catalogs.items()):
            if loc == source:
                continue
            vals = {cat.get(k) for k in keys if cat.get(k) is not None}
            if len(vals) > 1:
                add("DRIFTS", "split-translation", ",".join(sorted(keys)), f"Same source '{text}' translated {len(vals)} ways.", loc)

    return finish(findings, len(src), sorted(catalogs))


def finish(findings, n_strings, locales):
    order = {t: i for i, t in enumerate(TIERS)}
    findings.sort(key=lambda f: (order[f["tier"]], f["rule"], f.get("locale", ""), f["key"]))
    counts = {t: sum(1 for f in findings if f["tier"] == t) for t in TIERS}
    if counts["BREAKS"]:
        verdict = "HOLD"
    elif counts["MISLEADS"]:
        verdict = "SHIP WITH DEBT"
    else:
        verdict = "CLEAN" if not counts["DRIFTS"] else "CLEAN WITH DRIFT"
    return {"verdict": verdict, "counts": counts, "strings": n_strings, "locales": locales, "findings": findings}


# ---------------------------------------------------------------- code scan

CODE_RULES = [
    ("BREAKS", "concatenated-sentence", re.compile(r"""["'`][^"'`\n]*[A-Za-z]\s["'`]\s*\+\s*[\w.()\[\]]+\s*\+\s*["'`]\s*[A-Za-z]"""),
     "Sentence glued around a variable; word order differs per language. Use one message with a placeholder."),
    ("BREAKS", "plural-hack", re.compile(r"""===?\s*1\s*\?\s*(["'`])\1\s*:\s*(["'`])s\2|===?\s*1\s*\?\s*(["'`])s?\3\s*:\s*(["'`])s\4"""),
     "Two-form plural hack; many languages have more forms. Use ICU plural or Intl.PluralRules."),
    ("DRIFTS", "unlocalized-date", re.compile(r"\.toLocale(?:Date|Time)?String\(\s*\)"),
     "Date/number formatted without a locale; pass the user's locale (Intl.DateTimeFormat)."),
    ("MISLEADS", "glyph-name", re.compile(r"""aria-label\s*=\s*["'](?:x|close icon|trash|trash icon|icon|button|menu icon)["']""", re.I),
     "Accessible name describes the glyph; name the action ('Close dialog', 'Delete project')."),
]

CODE_EXT = (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".swift", ".kt", ".dart", ".py", ".rb", ".php")


def scan_code(root):
    out = []
    paths = [root] if os.path.isfile(root) else []
    if not paths:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in ("node_modules", ".git", "dist", "build", "vendor")]
            for fn in files:
                if fn.endswith(CODE_EXT):
                    paths.append(os.path.join(d, fn))
    for p in sorted(paths):
        try:
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for tier, rule, rx, why in CODE_RULES:
                if rx.search(line):
                    out.append({"tier": tier, "rule": rule, "key": f"{p}:{i}", "why": why, "text": line.strip()[:160]})
    return out


# ---------------------------------------------------------------- rendering

def to_markdown(res):
    lines = [f"# String census: {res['verdict']}", "",
             f"{res['strings']} source strings, locales: {', '.join(res['locales'])}", "",
             "| Tier | Count |", "| --- | --- |"]
    for t in TIERS:
        lines.append(f"| {t} | {res['counts'][t]} |")
    for t in TIERS:
        rows = [f for f in res["findings"] if f["tier"] == t]
        if not rows:
            continue
        lines += ["", f"## {t}", "", "| Rule | Locale | Key / location | Text | Why |", "| --- | --- | --- | --- | --- |"]
        for f in rows:
            txt = (f.get("text") or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {f['rule']} | {f.get('locale', '')} | `{f['key']}` | {txt} | {f['why']} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit interface strings across locales.")
    ap.add_argument("catalogs", nargs="+", help="locale files (.json, .arb, .strings); locale taken from file name")
    ap.add_argument("--source", required=True, help="source locale, e.g. en")
    ap.add_argument("--card", help="census card JSON (glossary, case_policy, slots, roles, ...)")
    ap.add_argument("--code", action="append", default=[], help="source dir/file to scan for glued strings")
    ap.add_argument("--colon", action="store_true", help="treat :name as a placeholder (Laravel style)")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    a = ap.parse_args(argv)
    cats = {}
    for p in a.catalogs:
        cats[locale_from_path(p)] = load_catalog(p)
    card = json.load(open(a.card, encoding="utf-8")) if a.card else {}
    res = census(cats, a.source, card, a.colon)
    extra = []
    for c in a.code:
        extra += scan_code(c)
    if extra:
        res = finish(res["findings"] + extra, res["strings"], res["locales"])
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.format == "json" else to_markdown(res))
    return {"HOLD": 2, "SHIP WITH DEBT": 1}.get(res["verdict"], 0)


if __name__ == "__main__":
    sys.exit(main())
