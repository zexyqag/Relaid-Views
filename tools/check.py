#!/usr/bin/env python3
"""Check the packs (views of apps) in this repo and build index.json.

    python3 tools/check.py              check every pack, and that index.json is current
    python3 tools/check.py --write      the same, then write index.json
    python3 tools/check.py --base REF   also: a pack whose view.json changed since REF has a higher version
    python3 tools/check.py --self-test  run tools/conformance.json

Standard library only, Python 3.8 or newer.

Relaid applies the same pack rules again on the phone before it installs anything; this check is
there so a mistake shows up in review instead of on someone's phone. Problems come in two kinds:

  refused   the phone would refuse the whole pack
  mistake   the phone would accept the pack but ignore that part (a colour its skin rules drop) or
            it is almost certainly a typo (a screen name that is not an id); the check fails on it too

tools/conformance.json holds cases with the expected verdict of each. Relaid's own validator runs
the same cases in its tests, which keeps the two in step.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMAT = 3

PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+")
VIEW = re.compile(r"[a-z][a-z0-9-]{0,31}")
BUILT_IN = {"generic", "pictures"}  # Relaid's own views of every app; no pack may take one
SELECTOR_KINDS = ("id", "id~", "text", "text~", "desc", "desc~", "class", "is", "nth")
SELECTOR_RELATIONS = ("in", "parent", "has", "not")
SELECTOR_STATES = ("clickable", "long-clickable", "editable", "scrollable", "checkable", "checked", "selected", "focused", "heading", "password")
CONFIRMS = {"slide"}
PERFORMS = {"click", "swipe-right", "swipe-left", "swipe-up", "swipe-down"}
TONES = {"primary", "secondary", "muted", "destructive"}
KEYBOARDS = {"number", "phone", "email", "text"}
SCROLLS = {"drag"}
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
SCREEN_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
INT = re.compile(r"[+-]?[0-9]+")

# Field types, as Relaid reads them. "?" marks a field that may also be null.
PART = {"select": "str", "as": "str?", "label": "str?", "tone": "str?", "confirm": "str?", "perform": "str?", "icon": "str?",
        "keyboard": "str?", "scroll": "str?", "parts": "str?", "press": "str?", "total": "int?"}
PALETTE = {"accent": "str?", "background": "str?", "surface": "str?", "text": "str?", "muted": "str?", "onAccent": "str?"}
THEME = {"accent": "str?", "light": (PALETTE,), "dark": (PALETTE,), "corners": "str?", "header": "str?", "cards": "str?"}
SCREEN = {"name": "str", "displayName": "str?", "when": "strs", "activity": "str?", "secure": "bool", "priority": "int", "parts": [PART]}
PACK = {"theme": (THEME,), "screens": [SCREEN]}
# Each role a part can have, and the options it takes (Relaid's ViewFormat.ROLES); None: a bare label.
ROLES = {
    None: {"label"}, "hidden": set(), "text": set(), "heading": set(), "picture": {"label"}, "title": set(), "hero": set(),
    "list": {"scroll"}, "field": {"label", "keyboard"}, "action": {"label", "tone", "confirm", "perform"},
    "option": {"label", "tone"}, "tab": {"label", "icon"}, "person": set(), "row": {"parts", "press"}, "pin": {"label", "total"},
    "unread": set(),
}
SINGLE = {"title", "hero", "list", "pin"}
OPTIONS = ("label", "tone", "confirm", "perform", "icon", "keyboard", "scroll", "parts", "press", "total")
PACK_META = {"app": "str", "view": "str", "name": "str", "version": "int", "description": "str", "permissions": "strs"}
# What a pack may ask for beyond shaping screens (Relaid's Packs.PERMISSIONS); the owner grants it.
PERMISSIONS = ("touch", "pictures")

# The skin rules, exactly as Relaid's relaid.views.Skin applies them (a part that breaks them is
# ignored on the phone): colours #RRGGBB; an accent more than 30 degrees of hue from the client's
# destructive red unless nearly grey; a palette complete, with text and muted text at 4.5:1 and the
# accent and the destructive red at 3:1 against background and surface, onAccent at 3:1 against the
# accent; fixed values for corners, header and cards; tab icons from a fixed set.
CORNERS = ("square", "rounded", "round")
HEADERS = ("bar", "plain", "accent")
CARDS = ("outlined", "filled", "flat")
ICONS = ("home", "list", "people", "person", "wallet", "card", "search", "settings", "bell", "chart", "star", "chat", "grid")
DANGER_LIGHT = "#c63b3b"
DANGER_DARK = "#ff6b6b"
TEXT_CONTRAST = 4.5
UI_CONTRAST = 3.0
MIN_HUE_APART = 30.0
GREY_SATURATION = 0.2


def is_color(s):
    return isinstance(s, str) and HEX_COLOR.fullmatch(s) is not None


def channels(h):
    return [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]


def luminance(h):
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels(h)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hue_saturation(h):
    r, g, b = channels(h)
    hi, lo = max(r, g, b), min(r, g, b)
    d = hi - lo
    if d == 0:
        return 0.0, 0.0
    light = (hi + lo) / 2
    sat = d / (1 - abs(2 * light - 1))
    if hi == r:
        hue = 60 * (((g - b) / d) % 6)
    elif hi == g:
        hue = 60 * ((b - r) / d + 2)
    else:
        hue = 60 * ((r - g) / d + 4)
    return (hue + 360 if hue < 0 else hue), sat


def accent_problem(accent):
    if not is_color(accent):
        return "is not #RRGGBB"
    hue, sat = hue_saturation(accent)
    danger = hue_saturation(DANGER_LIGHT)[0]
    apart = min(abs(hue - danger), 360 - abs(hue - danger))
    return "is too close to the destructive red" if sat >= GREY_SATURATION and apart <= MIN_HUE_APART else None


def palette_problem(pal, scheme, theme_accent):
    parts = [(k, pal.get(k)) for k in ("background", "surface", "text", "muted")]
    for k, v in parts:
        if v is None:
            return f"has no {k}"
    for k, v in parts + [("accent", pal.get("accent")), ("onAccent", pal.get("onAccent"))]:
        if v is not None and not is_color(v):
            return f"{k} is not #RRGGBB"
    accent = pal.get("accent")
    if accent is None and theme_accent is not None and accent_problem(theme_accent) is None:
        accent = theme_accent
    if accent is None:
        return "has no usable accent"
    why = accent_problem(accent)
    if why:
        return f"accent {why}"
    on = pal.get("onAccent")
    if on is not None and contrast(on, accent) < UI_CONTRAST:
        return "onAccent on accent is %.2f:1, needs %.1f:1" % (contrast(on, accent), UI_CONTRAST)
    danger = DANGER_DARK if scheme == "dark" else DANGER_LIGHT
    for name, color, need in (("text", pal["text"], TEXT_CONTRAST), ("muted", pal["muted"], TEXT_CONTRAST),
                              ("accent", accent, UI_CONTRAST), ("destructive red", danger, UI_CONTRAST)):
        for on_name, against in (("background", pal["background"]), ("surface", pal["surface"])):
            c = contrast(color, against)
            if c < need:
                return "%s on %s is %.2f:1, needs %.1f:1" % (name, on_name, c, need)
    return None


def theme_problems(t):
    """Each part of a theme the phone ignores, with why, in Relaid's order."""
    out = []
    if t.get("accent") is not None:
        why = accent_problem(t["accent"])
        if why:
            out.append(("theme.accent", why))
    for scheme in ("light", "dark"):
        if t.get(scheme) is not None:
            why = palette_problem(t[scheme], scheme, t.get("accent"))
            if why:
                out.append((f"theme.{scheme}", why))
    return out


def ignored_theme_parts(pack):
    """The theme parts the phone ignores in a pack (for tools/conformance.json)."""
    t = pack.get("theme") if isinstance(pack, dict) else None
    return sorted(key for key, _ in theme_problems(t)) if isinstance(t, dict) else []

class Problems:
    def __init__(self):
        self.items = []

    def refused(self, where, msg):
        self.items.append(("refused", where, msg))

    def mistake(self, where, msg):
        self.items.append(("mistake", where, msg))

    def any(self, kind=None):
        return any(k == kind or kind is None for k, _, _ in self.items)


def utf16_len(s):
    """String length as Relaid counts it (UTF-16 code units)."""
    return len(s.encode("utf-16-le")) // 2


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and -2**31 <= v < 2**31


def type_ok(v, t):
    nullable = isinstance(t, str) and t.endswith("?")
    if v is None:
        return nullable or isinstance(t, tuple)
    base = t.rstrip("?") if isinstance(t, str) else t
    if base == "str":
        return isinstance(v, str)
    if base == "strs":
        return isinstance(v, list) and all(isinstance(x, str) for x in v)
    if base == "bool":
        return isinstance(v, bool)
    if base == "int":
        return is_int(v)
    if base == "map":
        return isinstance(v, dict) and all(isinstance(x, str) or x is None for x in v.values())
    if isinstance(base, list):
        return isinstance(v, list) and all(isinstance(x, dict) for x in v)
    if isinstance(base, tuple):
        return isinstance(v, dict)
    raise AssertionError(t)


def check_object(obj, spec, required, where, p):
    """Types, required keys and unknown keys (refused: Relaid parses packs strictly). Recurses."""
    if not isinstance(obj, dict):
        p.refused(where, "must be an object")
        return False
    ok = True
    for key in sorted(required - obj.keys()):
        p.refused(where, f"'{key}' is required")
        ok = False
    for key, v in obj.items():
        t = spec.get(key)
        if t is None:
            p.refused(where, f"unknown key '{key}'")
            ok = False
            continue
        if not type_ok(v, t):
            p.refused(where, f"'{key}' has the wrong type")
            ok = False
            continue
        if isinstance(t, list):
            inner = t[0]
            req = {k for k, kt in inner.items() if kt == "str"}
            for i, item in enumerate(v):
                ok &= check_object(item, inner, req, f"{where} {key}[{i}]", p)
        elif isinstance(t, tuple) and v is not None:
            inner = t[0]
            req = {k for k, kt in inner.items() if kt == "str"}
            ok &= check_object(v, inner, req, f"{where} {key}", p)
    return ok


def selector_parts(s):
    """Split on ' & ' outside parentheses, as Relaid does; raises ValueError naming the problem."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"selector '{s}' closes a parenthesis it never opened")
        elif depth == 0 and s.startswith(" & ", i):
            out.append(s[start:i])
            start = i + 3
            i += 2
        i += 1
    if depth != 0:
        raise ValueError(f"selector '{s}' leaves a parenthesis open")
    out.append(s[start:])
    out = [x.strip() for x in out]
    if any(not x for x in out):
        raise ValueError(f"selector '{s}' has an empty part")
    return out


def selector_relation(part):
    o = part.find("(")
    if o <= 0 or not part.endswith(")") or part[:o] not in SELECTOR_RELATIONS:
        return None
    return part[:o], part[o + 1:-1]


def selector_problem(s):
    """Why a selector does not compile, as Relaid compiles it, or None."""
    try:
        parts = selector_parts(s)
    except ValueError as e:
        return str(e)
    for part in parts:
        rel = selector_relation(part)
        if rel:
            why = selector_problem(rel[1])
            if why:
                return why
            continue
        colon = part.find(":")
        if colon <= 0:
            return f"selector part '{part}' needs kind:value or relation(selector)"
        kind, value = part[:colon], part[colon + 1:]
        if not value:
            return f"selector part '{part}' has no value"
        if kind not in SELECTOR_KINDS:
            return f"unknown selector kind '{kind}' in '{part}' (use {', '.join(SELECTOR_KINDS)}, {', '.join(r + '(...)' for r in SELECTOR_RELATIONS)})"
        if kind == "is" and value not in SELECTOR_STATES:
            return f"unknown state '{value}' in '{part}' (use {', '.join(SELECTOR_STATES)})"
        if kind == "nth" and not (INT.fullmatch(value) and int(value) >= 1):
            return f"nth needs a position from 1 in '{part}'"
    return None


def selector_kinds(s):
    """Every condition kind and relation a selector uses, nested ones too (for pack formats)."""
    out = set()

    def collect(part):
        rel = selector_relation(part)
        if rel:
            out.add(rel[0])
            for x in selector_parts(rel[1]):
                collect(x)
        else:
            out.add(part.split(":", 1)[0])
    for x in selector_parts(s):
        collect(x)
    return out


def check_pack(app, pack, where, p):
    """Every rule for one view file. Returns the screen names in order."""
    if not PACKAGE.fullmatch(app or ""):
        p.refused(where, f"'{app}' is not a package name")
        return []
    if not check_object(pack, PACK, {"screens"}, where, p):
        return []
    if not pack["screens"]:
        p.refused(where, "a pack needs at least one screen")
        return []
    theme = pack.get("theme")
    if theme is not None:
        for key, allowed in (("corners", CORNERS), ("header", HEADERS), ("cards", CARDS)):
            if theme.get(key) is not None and theme[key] not in allowed:
                p.refused(where, f"unknown theme {key} '{theme[key]}' (use: {', '.join(allowed)})")
        for key, why in theme_problems(theme):
            p.mistake(where, f"{key} {why} (the phone ignores it)")
    names = []
    for s in pack["screens"]:
        name = s["name"]
        at = f"{where} screen '{name}'"
        if name in names:
            p.refused(at, "the name is used twice")
        names.append(name)
        if not SCREEN_NAME.fullmatch(name):
            p.mistake(at, "name should be lowercase letters, digits and dashes (it is the screen's stable id)")
        shown = s.get("displayName")
        if shown is not None:
            if not (1 <= utf16_len(shown) <= 60) or "\n" in shown:
                p.refused(at, "displayName must be one line, at most 60 characters")
            elif CONTROL.search(shown):
                p.mistake(at, "displayName contains a control character")
        for j, sel in enumerate(s.get("when", [])):
            why = selector_problem(sel)
            if why:
                p.refused(f"{at} when[{j}]", why)
        parts = s.get("parts", [])
        for role in SINGLE:
            if sum(1 for x in parts if x.get("as") == role) > 1:
                p.refused(at, f"more than one '{role}'")
        for j, x in enumerate(parts):
            pat = f"{at} part {j + 1}"
            role = x.get("as")
            if role not in ROLES:
                p.refused(pat, f"unknown role '{role}' (use {', '.join(r for r in ROLES if r)})")
                continue
            for opt in OPTIONS:
                if x.get(opt) is not None and opt not in ROLES[role]:
                    p.refused(pat, f"'{role or 'label'}' takes no '{opt}'")
            if role is None and x.get("label") is None:
                p.refused(pat, "a rule without a role needs a label")
            label = x.get("label")
            if label is not None and (not label.strip() or utf16_len(label) > 60 or "\n" in label):
                p.refused(pat, "a label must be one line, at most 60 characters")
            for opt, allowed in (("tone", TONES), ("confirm", CONFIRMS), ("perform", PERFORMS), ("icon", set(ICONS)),
                                 ("keyboard", KEYBOARDS), ("scroll", SCROLLS)):
                if x.get(opt) is not None and x[opt] not in allowed:
                    p.refused(pat, f"unknown {opt} '{x[opt]}' (use: {', '.join(sorted(allowed))})")
            if x.get("total") is not None and not 1 <= x["total"] <= 12:
                p.refused(pat, "total must be 1 to 12")
            for opt in ("select", "parts", "press"):
                if x.get(opt) is not None:
                    why = selector_problem(x[opt])
                    if why:
                        p.refused(f"{pat} {opt}", why)
    return names

def no_duplicate_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key '{k}'")
        seen[k] = v
    return seen


def load_json(path, p, where):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    except (ValueError, UnicodeDecodeError) as e:
        p.refused(where, f"not valid JSON: {e}")
        return None


def tracked_files():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
        return [x for x in out.stdout.decode().split("\0") if x]
    except (OSError, subprocess.CalledProcessError):
        return None


ALLOWED = {".gitignore", "README.md", "LICENSE", "index.json", "tools/check.py", "tools/conformance.json",
           ".github/workflows/check.yml"}
PACK_FILE = re.compile(r"packs/([^/]+)/([^/]+)/(pack\.json|view\.json)")
FIXTURE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\.xml")
FIXTURE_FILE = re.compile(r"packs/([^/]+)/([^/]+)/fixtures/([a-z0-9][a-z0-9._-]{0,63}\.xml|expect\.json)")

# Captured screens of a pack's app and what the pack must make of them. Relaid's tests run them
# (PackFixturesTest); the phone never sees them, so every problem here is a mistake.
PROGRESS_EXPECT = {"filled": "int", "total": "int?", "counted": "bool"}
EXPECT = {
    "why": "str?", "fixture": "str", "screen": "str?", "secure": "bool", "title": "str?",
    "shows": "strs", "hides": "strs", "actions": "strs", "options": "strs", "tabs": "strs",
    "slides": "strs", "fields": "map", "keypad": "int", "progress": (PROGRESS_EXPECT,), "hero": "str?",
    "avatars": "strs", "headings": "strs",
}


def check_fixtures(d, names, p):
    """A pack's fixtures/: an expect.json naming captures that exist and screens the view has."""
    fx = d / "fixtures"
    if not fx.exists():
        return
    where = f"packs/{d.parent.name}/{d.name}/fixtures"
    if fx.is_symlink() or not fx.is_dir():
        p.mistake(where, "must be a plain folder")
        return
    exp = fx / "expect.json"
    if not exp.is_file() or exp.is_symlink():
        p.mistake(where, "needs an expect.json saying what the pack makes of each screen")
        return
    try:
        cases = json.loads(exp.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    except (ValueError, UnicodeDecodeError) as e:
        p.mistake(f"{where}/expect.json", f"not valid JSON: {e}")
        return
    if not isinstance(cases, list) or not cases:
        p.mistake(f"{where}/expect.json", "must be a non-empty array of expectations")
        return
    used = set()
    for i, c in enumerate(cases):
        at = f"{where}/expect.json [{i}]"
        sub = Problems()
        check_object(c, EXPECT, {"fixture"}, at, sub)
        for _, w, m in sub.items:
            p.mistake(w, m)
        if not isinstance(c, dict) or not isinstance(c.get("fixture"), str):
            continue
        name = c["fixture"]
        used.add(name)
        if not FIXTURE_NAME.fullmatch(name) or not (fx / name).is_file():
            p.mistake(at, f"no fixture '{name}'")
        if isinstance(c.get("screen"), str) and c["screen"] not in names:
            p.mistake(at, f"no screen '{c['screen']}' in this view")
    for f in sorted(fx.iterdir()):
        if f.name == "expect.json":
            continue
        if f.is_symlink():
            p.mistake(f"{where}/{f.name}", "must not be a symlink")
            continue
        if f.suffix != ".xml":
            continue
        try:
            if ET.parse(f).getroot().tag != "snapshot":
                p.mistake(f"{where}/{f.name}", "is not a Relaid snapshot (no <snapshot>; capture it with the host's dump)")
        except ET.ParseError as e:
            p.mistake(f"{where}/{f.name}", f"not valid XML: {e}")
        if f.name not in used:
            p.mistake(f"{where}/{f.name}", "is not used in expect.json")


def build_index(p):
    """Check every pack and return the index they make."""
    files = tracked_files()
    if files is not None:
        for f in files:
            if f not in ALLOWED and not PACK_FILE.fullmatch(f) and not FIXTURE_FILE.fullmatch(f):
                p.mistake(f, "unexpected file (packs/<app>/<view>/ holds pack.json, view.json and fixtures/)")
    packs_dir = ROOT / "packs"
    entries = []
    dirs = lambda of: sorted((x for x in of.iterdir() if x.is_dir()), key=lambda x: x.name)
    views = [(a, v) for a in dirs(packs_dir) for v in dirs(a)] if packs_dir.is_dir() else []
    for a, d in views:
        where = f"packs/{a.name}/{d.name}"
        bad_link = [f.name for f in (a, d, d / "pack.json", d / "view.json") if f.is_symlink()]
        if bad_link:
            p.refused(where, f"{', '.join(bad_link)} must not be a symlink")
            continue
        if not (d / "pack.json").is_file() or not (d / "view.json").is_file():
            p.refused(where, "needs pack.json and view.json")
            continue
        meta = load_json(d / "pack.json", p, f"{where}/pack.json")
        if meta is None or not check_object(meta, PACK_META, {"app", "view", "name", "version"}, f"{where}/pack.json", p):
            continue
        if meta["app"] != a.name:
            p.refused(f"{where}/pack.json", f"declares app {meta['app']}, but the folder is {a.name}")
            continue
        if meta["view"] != d.name:
            p.refused(f"{where}/pack.json", f"declares view {meta['view']}, but the folder is {d.name}")
            continue
        if not VIEW.fullmatch(meta["view"]):
            p.refused(f"{where}/pack.json", f"view '{meta['view']}' must be lowercase letters, digits and dashes")
            continue
        if meta["view"] in BUILT_IN:
            p.refused(f"{where}/pack.json", f"view '{meta['view']}' is one of Relaid's own")
            continue
        if meta["version"] < 1:
            p.refused(f"{where}/pack.json", "version must be at least 1")
        if not meta["name"].strip() or utf16_len(meta["name"]) > 40 or CONTROL.search(meta["name"]):
            p.mistake(f"{where}/pack.json", "name should be one line, at most 40 characters")
        desc = meta.get("description", "")
        if utf16_len(desc) > 400 or CONTROL.search(desc):
            p.mistake(f"{where}/pack.json", "description should be one paragraph, at most 400 characters")
        raw = (d / "view.json").read_bytes()
        view = load_json(d / "view.json", p, f"{where}/view.json")
        if view is None:
            continue
        names = check_pack(meta["app"], view, f"{where}/view.json", p)
        check_fixtures(d, names, p)
        permissions = meta.get("permissions", [])
        for x in permissions:
            if x not in PERMISSIONS:
                p.refused(f"{where}/pack.json", f"unknown permission '{x}' (use: {', '.join(PERMISSIONS)})")
        if len(set(permissions)) != len(permissions):
            p.refused(f"{where}/pack.json", "a permission is listed twice")
        screens = view.get("screens") if isinstance(view, dict) and isinstance(view.get("screens"), list) else []
        def using(test):
            return [x.get("name") for x in screens if isinstance(x, dict) and any(isinstance(q, dict) and test(q) for q in x.get("parts") or [])]
        touching = using(lambda q: str(q.get("perform") or "").startswith("swipe-") or q.get("scroll") == "drag")
        if "touch" not in permissions and touching:
            p.refused(f"{where}/pack.json", f"screens {touching} swipe or drag, which needs the permission \"touch\"")
        picturing = using(lambda q: q.get("as") == "picture")
        if "pictures" not in permissions and picturing:
            p.refused(f"{where}/pack.json", f"screens {picturing} show pictures, which needs the permission \"pictures\"")
        entries.append({
            "app": meta["app"],
            "view": meta["view"],
            "name": meta["name"],
            "version": meta["version"],
            "format": format_of(view),
            "description": desc,
            "path": f"packs/{meta['app']}/{meta['view']}/view.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "screens": names,
            "permissions": permissions,
        })
    for app in sorted({e["app"] for e in entries}):
        names = [e["name"] for e in entries if e["app"] == app]
        if len(set(names)) != len(names):
            p.refused(f"packs/{app}", "an app's views need distinct names")
    return {"format": FORMAT, "packs": entries}


# The pack format that introduced each view feature after format 1, as "key.path" or
# "key.path=value" (arrays are transparent: "screens.parts.as=picture"), or "selector:<kind>" for a
# selector kind or relation used anywhere. A pack needs the highest format of the features it uses.
# Relaid's Packs.FORMAT_SINCE is the same table; add to both with every feature.
FORMAT_SINCE = {
    "screens.parts.as=unread": 2,
}
SELECTOR_PATHS = ("select", "when", "parts", "press")


def format_of(view):
    """The pack format a view file needs."""
    used = set()

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                q = f"{path}.{k}" if path else k
                used.add(q)
                walk(x, q)
        elif isinstance(v, list):
            for x in v:
                walk(x, path)
        elif isinstance(v, str):
            used.add(f"{path}={v}")
            if path.endswith(SELECTOR_PATHS):
                try:
                    used.update("selector:" + k for k in selector_kinds(v))
                except ValueError:
                    pass

    walk(view, "")
    return max([FORMAT_SINCE.get(u, 1) for u in used] or [1])

def encode_index(index):
    """The exact bytes Relaid's own index builder writes."""
    return json.dumps(index, indent=4, ensure_ascii=False) + "\n"


def git_show(ref, path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def check_versions(base, index, p):
    """A pack whose view.json changed since [base] must have a higher version (phones show it as an update)."""
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], capture_output=True)
    if r.returncode != 0:
        p.refused("--base", f"'{base}' is not a commit here")
        return
    for e in index["packs"]:
        old_view = git_show(base, e["path"])
        old_meta = git_show(base, f"packs/{e['app']}/{e['view']}/pack.json")
        if old_view is None or old_meta is None:
            continue  # a new pack
        try:
            old_version = json.loads(old_meta)["version"]
        except (ValueError, KeyError, TypeError):
            continue
        where = f"packs/{e['app']}/{e['view']}/pack.json"
        if e["version"] < old_version:
            p.refused(where, f"version went down from {old_version} to {e['version']}")
        elif hashlib.sha256(old_view).hexdigest() != e["sha256"] and e["version"] == old_version:
            p.refused(where, f"view.json changed, so the version must go above {old_version}")


def report(p):
    gh = os.environ.get("GITHUB_ACTIONS") == "true"
    for kind, where, msg in p.items:
        line = f"{kind}: {where}: {msg}"
        if gh:
            path = where.split(" ")[0]
            file_part = f" file={path}" if (ROOT / path).is_file() else ""
            print(f"::error{file_part}::{line}".replace("\n", "%0A"))
        else:
            print(line)


def self_test():
    cases = json.loads((ROOT / "tools" / "conformance.json").read_text(encoding="utf-8"))["cases"]
    wrong = []
    for c in cases:
        p = Problems()
        check_pack(c["app"], c["pack"], "case", p)
        phone_ok = not p.any("refused")
        check_ok = not p.items
        if phone_ok != c["phone"] or check_ok != c["check"]:
            got = f"phone {'accepts' if phone_ok else 'refuses'}, check {'passes' if check_ok else 'fails'}"
            wrong.append(f"{c['why']}: got {got}; problems: {[m for _, _, m in p.items]}")
        elif "ignored" in c and ignored_theme_parts(c["pack"]) != sorted(c["ignored"]):
            wrong.append(f"{c['why']}: the phone would ignore {ignored_theme_parts(c['pack'])}, expected {sorted(c['ignored'])}")
    for w in wrong:
        print("conformance:", w)
    print(f"{len(cases) - len(wrong)} of {len(cases)} conformance cases agree")
    return 1 if wrong else 0


def main():
    ap = argparse.ArgumentParser(description="Check the packs and build index.json.")
    ap.add_argument("--write", action="store_true", help="write index.json")
    ap.add_argument("--base", help="git ref to compare versions against (a pull request's target)")
    ap.add_argument("--self-test", action="store_true", help="run tools/conformance.json")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    p = Problems()
    index = build_index(p)
    if args.base:
        check_versions(args.base, index, p)
    encoded = encode_index(index)
    current = (ROOT / "index.json").read_text(encoding="utf-8") if (ROOT / "index.json").is_file() else None
    if args.write and not p.any("refused"):
        (ROOT / "index.json").write_text(encoded, encoding="utf-8")
        current = encoded
    if current != encoded:
        p.refused("index.json", "out of date: run python3 tools/check.py --write and commit it")
    report(p)
    total = sum(len(e["screens"]) for e in index["packs"])
    if p.items:
        print(f"{len(p.items)} problem(s) in {len(index['packs'])} pack(s)")
        return 1
    print(f"ok: {len(index['packs'])} pack(s), {total} screen(s), index.json current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
