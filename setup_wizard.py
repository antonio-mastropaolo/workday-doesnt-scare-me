#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_wizard.py — Workday doesn't scare me! · workshop setup TUI
W&M CDSP · AI Programming Tutorial

One file, stdlib only. Run it from the terminal:

    python3 setup_wizard.py            # interactive wizard
    python3 setup_wizard.py --yes      # accept all defaults, no questions
    python3 setup_wizard.py --doctor   # environment checks only
    python3 setup_wizard.py --no-color # plain output

What it does
  1. checks your machine (Claude Desktop, Chrome, node/npx for the Gmail MCP)
  2. creates the demo folders  (~/demo-ai-cdsp, ~/scratch/run1..3)
  3. stages the three skills from the tutorial kit
  4. personalizes the three working prompts with YOUR trip, dates, worktag
  5. walks you through the Gmail connector, Claude in Chrome, and Duo 30-day trust
Nothing here touches credentials: SSO stays in your browser, Duo in your pocket.
"""

import argparse
import datetime as _dt
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

# ----------------------------------------------------------------------------
# palette — the deck's terminal look: W&M green, gold, mint
# ----------------------------------------------------------------------------

def _supports_color(force_off: bool) -> bool:
    if force_off or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()

class C:
    on = True
    @classmethod
    def _w(cls, code, s):
        return f"\033[{code}m{s}\033[0m" if cls.on else str(s)
    @classmethod
    def green(cls, s):  return cls._w("38;2;17;87;64", s)       # deep W&M green
    @classmethod
    def mint(cls, s):   return cls._w("38;2;120;190;160", s)    # body on dark
    @classmethod
    def bright(cls, s): return cls._w("1;38;2;234;255;245", s)  # headline
    @classmethod
    def gold(cls, s):   return cls._w("38;2;201;162;75", s)     # accent
    @classmethod
    def dim(cls, s):    return cls._w("2", s)
    @classmethod
    def bold(cls, s):   return cls._w("1", s)
    @classmethod
    def chip(cls, s, kind="ok"):
        if not cls.on:
            return f"[{s}]"
        bg = {"ok": "48;2;17;87;64;38;2;234;255;245",
              "warn": "48;2;201;162;75;38;2;21;33;27",
              "off": "48;2;60;70;64;38;2;200;210;204"}[kind]
        return f"\033[{bg}m {s} \033[0m"

OK   = lambda: C.mint("✓")
BAD  = lambda: C.gold("✗")
FLAG = lambda: C.gold("⚑")
PROMPT = lambda: C.gold("❯")

W = 76  # frame width

def hr(ch="─"):
    print(C.green(ch * W))

def say(s=""):
    print(s)

def title_block():
    print()
    hr("═")
    print(C.bright("  WORKDAY DOESN'T SCARE ME!") + C.dim("  · workshop setup"))
    print(C.mint("  Automating faculty workflows end to end — W&M CDSP · AI tutorial"))
    hr("═")
    print(C.dim("  gmail → receipts → expenses.csv → a Workday draft · you keep Submit"))
    print()

def step_header(n, total, label):
    print()
    print(C.gold(f"STEP {n}/{total}") + C.dim(" · ") + C.bright(label))
    hr()

def logline(tag, text, kind="ok"):
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    print(f" {C.dim(ts)} {C.chip(tag, kind)} {C.mint(text)}")

# ----------------------------------------------------------------------------
# input helpers — arrow-key menu when we have a real TTY, numbered otherwise
# ----------------------------------------------------------------------------

ASSUME_YES = False

def ask(question, default=""):
    if ASSUME_YES:
        print(f" {PROMPT()} {question} {C.dim('→ ' + (default or '(blank)'))}")
        return default
    hint = C.dim(f" [{default}]") if default else ""
    try:
        val = input(f" {PROMPT()} {C.bright(question)}{hint} ").strip()
    except EOFError:
        return default
    return val or default

def ask_yn(question, default=True):
    if ASSUME_YES:
        print(f" {PROMPT()} {question} {C.dim('→ ' + ('yes' if default else 'no'))}")
        return default
    d = "Y/n" if default else "y/N"
    try:
        val = input(f" {PROMPT()} {C.bright(question)} {C.dim('['+d+']')} ").strip().lower()
    except EOFError:
        return default
    if not val:
        return default
    return val.startswith("y")

def menu(question, options, default=0):
    """Arrow-key single select; graceful numbered fallback."""
    if ASSUME_YES:
        print(f" {PROMPT()} {question} {C.dim('→ ' + options[default])}")
        return default
    if not (sys.stdin.isatty() and sys.stdout.isatty() and os.name == "posix"):
        print(f" {PROMPT()} {C.bright(question)}")
        for i, o in enumerate(options):
            print(f"    {C.gold(str(i+1))} {o}")
        try:
            raw = input(f"   {C.dim('number')} [{default+1}] ").strip()
        except EOFError:
            return default
        try:
            return max(0, min(len(options) - 1, int(raw) - 1)) if raw else default
        except ValueError:
            return default
    import termios, tty
    idx = default
    print(f" {PROMPT()} {C.bright(question)}  {C.dim('↑/↓ move · enter select')}")
    def draw(first=False):
        if not first:
            sys.stdout.write(f"\033[{len(options)}A")
        for i, o in enumerate(options):
            marker = C.gold("❯ ") if i == idx else "  "
            line = C.bright(o) if i == idx else C.mint(o)
            sys.stdout.write("\033[2K    " + marker + line + "\n")
        sys.stdout.flush()
    draw(first=True)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    idx = (idx - 1) % len(options); draw()
                elif seq == "[B":
                    idx = (idx + 1) % len(options); draw()
            elif ch in ("\r", "\n"):
                return idx
            elif ch in ("q", "\x03"):
                raise KeyboardInterrupt
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

class Spinner:
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    def __init__(self, text):
        self.text, self._stop = text, threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
    def _run(self):
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r {C.gold(self.FRAMES[i % 10])} {C.mint(self.text)} ")
            sys.stdout.flush(); i += 1; time.sleep(0.08)
    def __enter__(self):
        if sys.stdout.isatty():
            self._t.start()
        return self
    def __exit__(self, *a):
        self._stop.set()
        if self._t.is_alive():
            self._t.join()
        sys.stdout.write("\r\033[2K")

# ----------------------------------------------------------------------------
# environment checks
# ----------------------------------------------------------------------------

def _which(cmd):
    return shutil.which(cmd) is not None

def _app_installed(name):
    if platform.system() != "Darwin":
        return False
    return any((Path(root) / f"{name}.app").exists()
               for root in ("/Applications", str(Path.home() / "Applications")))

def detect_chrome_extension(needle="claude"):
    """Scan Chrome profiles' Preferences for an installed extension whose
    manifest name contains `needle`. Returns (found, where)."""
    roots = [Path.home() / "Library/Application Support/Google/Chrome",
             Path.home() / ".config/google-chrome"]
    hits = []
    for root in roots:
        if not root.exists():
            continue
        for prof in root.iterdir():
            if not prof.is_dir() or not (
                    prof.name == "Default" or prof.name.startswith("Profile")):
                continue
            for fname in ("Preferences", "Secure Preferences"):
                f = prof / fname
                if not f.exists():
                    continue
                try:
                    data = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    continue
                settings = (data.get("extensions", {}) or {}).get("settings", {}) or {}
                for meta in settings.values():
                    name = ((meta or {}).get("manifest", {}) or {}).get("name", "")
                    if needle in name.lower():
                        hits.append(f"{name} · {prof.name}")
    return (len(hits) > 0, hits[0] if hits else "")

def pause(msg="press Enter when done"):
    if ASSUME_YES:
        return
    try:
        input(f"   {C.dim(msg + ' …')} ")
    except EOFError:
        pass

def run_checks():
    mac = platform.system() == "Darwin"
    ext_found, ext_where = detect_chrome_extension()
    checks = [
        ("macOS", mac, "this workshop targets the Mac you carry"),
        ("Claude Desktop", _app_installed("Claude"), "free download → claude.ai/download"),
        ("Google Chrome", _app_installed("Google Chrome") or _which("google-chrome"),
         "needed for Skill 3 · Claude in Chrome"),
        ("Claude in Chrome", ext_found,
         ext_where if ext_found else "extension not detected — step 5 fixes this"),
        ("node / npx", _which("npx"), "runs the Gmail MCP server → nodejs.org (LTS)"),
        ("python3", True, "you're running it right now"),
    ]
    results = []
    with Spinner("checking your machine…"):
        time.sleep(0.6)
        for name, ok, note in checks:
            results.append((name, ok, note))
    good = True
    for name, ok, note in results:
        mark = OK() if ok else BAD()
        extra = C.dim("· " + note)
        print(f"   {mark} {C.bright(name.ljust(16))} {extra}")
        good &= ok or name in ("macOS",)  # macOS miss = warn, not fatal
    return results, good

# ----------------------------------------------------------------------------
# actions
# ----------------------------------------------------------------------------

def make_folders(base: Path, scratch: Path):
    made = []
    for p in (base, base / "expenses", scratch / "run1", scratch / "run2", scratch / "run3"):
        p.mkdir(parents=True, exist_ok=True)
        made.append(p)
    for p in made:
        logline("mkdir", str(p).replace(str(Path.home()), "~"))
    return made

def stage_skills(base: Path):
    """Find the four skills next to this script (folders or .skill zips) and stage them."""
    here = Path(__file__).resolve().parent
    names = ["expense-trip-harvester", "expense-trip-reconciler",
             "workday-expense-report", "expense-trip-pipeline"]
    dest = base / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    staged = []
    for n in names:
        src_dir = None
        for cand in (here / n, here / "skills" / n, here.parent / n):
            if (cand / "SKILL.md").exists():
                src_dir = cand; break
        zips = [z for z in (here / f"{n}.skill", here / "skills" / f"{n}.skill",
                            here.parent / f"{n}.skill") if z.exists()]
        if src_dir:
            shutil.copytree(src_dir, dest / n, dirs_exist_ok=True)
            staged.append(n); logline("skill", f"{n} · copied", "ok")
        elif zips:
            with zipfile.ZipFile(zips[0]) as zf:
                zf.extractall(dest)
            staged.append(n); logline("skill", f"{n} · unzipped", "ok")
        else:
            logline("skill", f"{n} · not found next to the wizard — add it in-app later", "warn")
    return dest, staged

PROMPT1 = """Search my Gmail (read-only) from {start} to {end} for everything I spent
on the {trip} trip — flights, hotel, registration, meals, taxis, visa,
baggage. Try receipt, invoice, e-ticket, confirmation, registration, payment,
folio, and the Portuguese ones too: recibo, fatura, nota fiscal, comprovante,
bilhete, reserva, pagamento. Dedupe by Message-ID.

Do the whole search three separate times into {scratch}/run1, run2, run3, and
don't let any run peek at the others. For each email, make a folder named
<date>_<domain>_<msgid8>: always save message.eml, and only save the
attachments if the body doesn't already show the amount. That's just a yes/no
check — don't read the number, don't add anything up.

Then SHA-256 everything and promote only the files whose hash shows up in all
three runs to {base}/expenses/, one copy each, same folder structure.

Flag anything that isn't 3/3 and say which run missed it. Give me file counts
per run and how many got promoted. No dollar amounts anywhere in the output."""

PROMPT2 = """Read every receipt in {base}/ — PDFs, photos, .eml — into
expenses.csv: date, vendor, amount, currency, category, justification. Dates
from the receipt, not the email. Three independent agents read each figure; a
judge from another model family rules on every value. LLMs-as-judge: subagents
retrieve each figure, master judge comments on every row. On disagreement,
leave blank and flag — never guess. Convert foreign amounts to {cur} at the
rate on the day of the expense following your university's travel policy
(W&M: translated receipts + the day-of-purchase historical rate attached to
each line). All sums in code. Show me the full printlog."""

PROMPT3 = """Fill my Workday expense report from {base}/expenses.csv, operating my
own visible Chrome through the Claude-in-Chrome extension in my logged-in
session — no headless, no separate profile. Open {workday}; when the SSO
screen appears, log "waiting for Duo…" and do nothing until I approve Duo on
my phone, then resume in the same tab. Create the expense report and fill one
line per CSV row, targeting fields by their visible labels: DATE → Expense
Date, CATEGORY → Expense Item, AMOUNT → Total Amount ({cur}), VENDOR +
JUSTIFICATION → Memo, my grant → Grant worktag ({worktag}). Attach the
matching receipt (pdf, png, or .eml) to each line. Recompute the CSV grand
total and line count in code and compare to what the form shows; a
blank/flagged amount fails the check. Then STOP — log "awaiting your Submit",
leave the draft open, and hand me the mouse. Never click Submit."""

def write_prompts(base: Path, cfg: dict):
    md = base / "my-prompts.md"
    fill = dict(start=cfg["start"], end=cfg["end"], trip=cfg["trip"],
                scratch=cfg["scratch"], base=cfg["base"], cur=cfg["currency"],
                worktag=cfg["worktag"], workday=cfg["workday"])
    body = (
        f"# My prompts — {cfg['trip']}\n\n"
        f"Personalized {_dt.date.today().isoformat()} for {cfg['name'] or 'you'}. "
        f"Paste these into Claude Desktop, in order.\n\n"
        f"## 1 · Harvest (→ expense-trip-harvester)\n\n{PROMPT1.format(**fill)}\n\n"
        f"## 2 · Reconcile (→ expense-trip-reconciler)\n\n{PROMPT2.format(**fill)}\n\n"
        f"## 3 · File in Workday (→ workday-expense-report)\n\n{PROMPT3.format(**fill)}\n\n"
        f"## One sentence, all three (→ expense-trip-pipeline)\n\n"
        f"Compile my travel expenses for the {cfg['trip']} trip, {cfg['start']} – "
        f"{cfg['end']}, and file them to my grant ({cfg['worktag']}) in Workday.\n"
    )
    md.write_text(body, encoding="utf-8")
    logline("write", str(md).replace(str(Path.home()), "~"))
    return md

def write_config(base: Path, cfg: dict, checks, connections=None):
    out = base / "setup.json"
    out.write_text(json.dumps({
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "user": {"name": cfg["name"], "email": cfg["email"]},
        "trip": {"label": cfg["trip"], "start": cfg["start"], "end": cfg["end"]},
        "paths": {"base": cfg["base"], "scratch": cfg["scratch"]},
        "workday": {"url": cfg["workday"], "grant_worktag": cfg["worktag"],
                    "currency": cfg["currency"]},
        "checks": {name: ok for name, ok, _ in checks},
        "connections": connections or {},
    }, indent=2), encoding="utf-8")
    logline("write", str(out).replace(str(Path.home()), "~"))
    return out

def _open(target):
    if platform.system() == "Darwin":
        subprocess.run(["open"] + (target if isinstance(target, list) else [target]),
                       check=False)

def connect_and_verify(cfg):
    """Interactive connect loop. Automates what a script honestly can:
    the extension is DETECTED from Chrome's own profile data and re-checked
    live; OAuth consents stay human (that's the security model, not a gap)."""
    conn = {"chrome_extension": False, "gmail_connector": False, "duo_trust_30d": False}

    # 1 · Claude in Chrome — detect, install, re-check until found
    say(); say(f"   {C.gold('1 · CLAUDE IN CHROME')}  {C.dim('(Skill 3 drives your visible browser)')}")
    found, where = detect_chrome_extension()
    while not found:
        say(f"   {BAD()} " + C.mint("not detected in any Chrome profile."))
        if ASSUME_YES or not ask_yn("Open the Chrome Web Store to install it now?", True):
            break
        _open("https://chromewebstore.google.com/search/Claude%20in%20Chrome")
        pause("install it, then press Enter to re-check")
        found, where = detect_chrome_extension()
    if found:
        say(f"   {OK()} " + C.mint(f"detected: {where}"))
    conn["chrome_extension"] = found

    # 2 · Gmail connector — Anthropic's in-app OAuth; open the app, verify by hand
    say(); say(f"   {C.gold('2 · GMAIL, READ-ONLY')}  {C.dim('(Skill 1 reads, never sends)')}")
    say(C.mint("       Claude Desktop → Settings → Connectors → Add connector → Gmail"))
    say(C.mint("       → Sign in with your university Google account. No JSON to edit."))
    if not ASSUME_YES and ask_yn("Open Claude Desktop at that screen now?", True):
        _open(["-a", "Claude"])
        pause("connect Gmail, then press Enter")
        conn["gmail_connector"] = ask_yn("Does the Gmail connector show as connected?", True)
    say(f"   {OK() if conn['gmail_connector'] else FLAG()} "
        + C.mint("gmail connector " + ("confirmed" if conn["gmail_connector"]
                 else "pending — the deck's Skill 1 setup slide has the clicks")))

    # 3 · Duo trust — the difference between one tap and zero taps
    say(); say(f"   {C.gold('3 · DUO · 30-DAY TRUST')}  {C.dim('(one tap → zero taps)')}")
    say(C.mint(f"       Sign in at {cfg['workday']} once; when Duo asks, check"))
    say(C.mint("       “remember me for 30 days.” The pause disappears — the agent"))
    say(C.mint("       runs start to finish by itself. Submit stays yours."))
    if not ASSUME_YES and ask_yn("Open your Workday sign-in now?", False):
        url = cfg["workday"] if cfg["workday"].startswith("http") else "https://" + cfg["workday"]
        _open(url)
        pause("sign in + Duo (tick the 30-day box), then press Enter")
        conn["duo_trust_30d"] = ask_yn("Did you tick “remember me for 30 days”?", True)
    say(f"   {OK() if conn['duo_trust_30d'] else FLAG()} "
        + C.mint("duo 30-day trust " + ("on — zero-tap runs" if conn["duo_trust_30d"]
                 else "not yet — first run will pause once for your tap")))
    return conn

def plan_lines(cfg):
    """The deterministic run, in the deck's appendix-log style."""
    b, s, tr = cfg["base"], cfg["scratch"], cfg["trip"]
    return [
        ("skill-1", f'gmail.search "{tr} receipts" · EN+PT terms · dedupe by Message-ID', "ok"),
        ("skill-1", f"3 independent runs → {s}/run1..3 · no peeking", "ok"),
        ("skill-1", f"SHA-256 cross-check · only 3/3 hashes promoted → {b}/expenses/", "ok"),
        ("skill-2", "each figure read by 3 agents · cross-family judge rules on every row", "ok"),
        ("skill-2", f"foreign amounts → {cfg['currency']} at day-of-purchase fx, rate on the line", "ok"),
        ("flag",    "any disagreement → cell left BLANK ⚑ · never guessed", "warn"),
        ("write",   f"{b}/expenses.csv · all sums in code, never the model", "ok"),
        ("skill-3", f"chrome (visible, your session) → {cfg['workday']} · fill by field labels", "ok"),
        ("skill-3", f"grant worktag {cfg['worktag']} · one receipt attached per line", "ok"),
        ("skill-3", "duo: tap once — or 30-day trust = zero taps", "ok"),
        ("verify",  "grand total + line count recomputed in code vs the form", "ok"),
        ("stop",    "awaiting your Submit · the agent never clicks it", "warn"),
    ]

def show_plan(cfg, save_to: Path = None):
    say()
    say(C.bright("  THE RUN, DETERMINISTIC — same steps, same order, every trip:"))
    say()
    for tag, text, kind in plan_lines(cfg):
        logline(tag, text, kind)
    say()
    say(C.dim("  reprint any time:  python3 setup_wizard.py --plan"))
    if save_to:
        plain = "\n".join(f"[{t}] {x}" for t, x, _ in plan_lines(cfg))
        save_to.write_text(
            f"# {cfg['trip']} · deterministic run plan · generated "
            f"{_dt.date.today().isoformat()}\n\n{plain}\n", encoding="utf-8")
        logline("write", str(save_to).replace(str(Path.home()), "~"))

def farewell(base: Path, staged):
    say()
    hr("═")
    say(C.bright("  FILED · NOT FEARED — you're configured."))
    hr("═")
    logline("done", f"folders ready · {len(staged)}/4 skills staged · prompts personalized")
    say()
    say(C.mint("  Next: open Claude Desktop, add the skills under Settings → Capabilities"))
    say(C.mint(f"  (staged in {str(base / 'skills').replace(str(Path.home()), '~')}),"))
    say(C.mint(f"  then paste Prompt 1 from {C.bold('my-prompts.md')} and watch the search."))
    say()
    say(C.dim("  if the demo gods frown, the run is pre-recorded — but they won't."))
    say()

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main():
    global ASSUME_YES
    ap = argparse.ArgumentParser(description="W&M CDSP tutorial setup wizard")
    ap.add_argument("--yes", action="store_true", help="accept all defaults")
    ap.add_argument("--doctor", action="store_true", help="checks only")
    ap.add_argument("--plan", action="store_true",
                    help="reprint the deterministic run plan from setup.json")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    ASSUME_YES = args.yes
    C.on = _supports_color(args.no_color)

    if args.plan:
        cfg_file = Path.home() / "demo-ai-cdsp" / "setup.json"
        if not cfg_file.exists():
            print("no setup.json yet — run the wizard first."); return 1
        saved = json.loads(cfg_file.read_text())
        cfg = dict(trip=saved["trip"]["label"], base=saved["paths"]["base"],
                   scratch=saved["paths"]["scratch"], currency=saved["workday"]["currency"],
                   workday=saved["workday"]["url"], worktag=saved["workday"]["grant_worktag"])
        title_block(); show_plan(cfg); print()
        return 0

    title_block()

    total = 5
    step_header(1, total, "Your machine")
    checks, _ = run_checks()
    if args.doctor:
        say(); say(C.dim("  doctor mode — nothing was changed."));  return 0

    step_header(2, total, "You and your trip")
    name  = ask("Your name", os.environ.get("USER", ""))
    email = ask("University email", "")
    trip  = ask("Trip / conference label", "ICSE 2026 Rio")
    start = ask("Search window start (emails may predate travel)", "Feb 1, 2026")
    end   = ask("Search window end", "May 31, 2026")
    workday = ask("Your Workday URL", "workday.wm.edu")
    worktag = ask("Grant worktag to charge", "GR005334")
    cur     = ask("Home currency", "USD")

    step_header(3, total, "Folders")
    base    = Path(ask("Working folder", str(Path.home() / "demo-ai-cdsp"))).expanduser()
    scratch = Path(ask("Scratch folder (3 independent runs)",
                       str(Path.home() / "scratch"))).expanduser()
    make_folders(base, scratch)

    step_header(4, total, "Skills + personalized prompts")
    _, staged = stage_skills(base)
    cfg = dict(name=name, email=email, trip=trip, start=start, end=end,
               workday=workday, worktag=worktag, currency=cur,
               base=str(base).replace(str(Path.home()), "~"),
               scratch=str(scratch).replace(str(Path.home()), "~"))
    write_prompts(base, cfg)

    step_header(5, total, "Connect & verify — the clicks that stay yours")
    conn = connect_and_verify(cfg)
    write_config(base, cfg, checks, conn)

    show_plan(cfg, save_to=base / "run-plan.txt")
    farewell(base, staged)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n" + C.dim("  cancelled — run me again any time.") if C.on
              else "\ncancelled — run me again any time.")
        sys.exit(130)
