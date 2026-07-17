# Workday doesn't scare me!

**Automating faculty expense reports end to end — Gmail → receipts → audited
CSV → a Workday draft.** The agent searches, verifies, converts, fills, and
attaches; you keep exactly three things: one OAuth consent, one Duo tap (zero
with 30-day trust), and the Submit button.

Companion kit for the W&M CDSP *AI Programming Tutorial* (Summer 2026),
by Antonio Mastropaolo (AURA Lab) and Oscar Chaparro (SEA Lab),
William & Mary — School of Computing, Data Sciences & Physics.

## Quickstart

```bash
git clone https://github.com/antonio-mastropaolo/workday-doesnt-scare-me.git
cd workday-doesnt-scare-me
python3 setup_wizard.py
```

That's the whole install. The wizard is a terminal UI that checks your
machine, creates the working folders, stages the skills, personalizes the
prompts with *your* trip and grant worktag, and walks you through the three
human clicks. Re-run it any time; it's idempotent.

```bash
python3 setup_wizard.py --doctor   # environment checks only
python3 setup_wizard.py --plan    # reprint the deterministic run plan
python3 setup_wizard.py --yes     # accept every default, ask nothing
```

## What's in the box

| Path | What it is |
|---|---|
| `setup_wizard.py` | The setup TUI. One file, standard library only. |
| `skills/expense-trip-harvester.skill` | Skill 1 — Gmail (read-only) → verified receipts. 3 independent runs, SHA-256 cross-check, dedupe by Message-ID. |
| `skills/expense-trip-reconciler.skill` | Skill 2 — receipts → audited `expenses.csv`. 3 extraction agents + a cross-family judge; day-of-purchase FX on every line; all sums in code; unclear values left BLANK, never guessed. |
| `skills/workday-expense-report.skill` | Skill 3 — CSV → Workday draft in your own visible Chrome. Fills by field labels, attaches every receipt, recomputes totals in code, **stops before Submit**. |
| `skills/expense-trip-pipeline.skill` | The orchestrator — one sentence runs all three in order. |
| `prompts.md` | The three full working prompts (the slides show them abridged) plus the one-sentence orchestrator. |
| `requirements.txt` | Spoiler: empty. Standard library only. |

## Requirements

The wizard runs on the Python 3 that ships with macOS (3.9+) — no `pip
install` needed. The workflow itself expects: **Claude Desktop** (a Pro
subscription is plenty), **Google Chrome** with the **Claude in Chrome**
extension, the **Gmail connector** enabled in Claude Desktop (Settings →
Connectors → Gmail, read-only), **node/npx** available on PATH, and your
**Duo** phone for one tap. The wizard checks all of this and — where a script
honestly can — fixes it: it detects the Chrome extension from Chrome's own
profile data and loops the install page until it appears. OAuth consents stay
human. That's the security model, not a gap.

## The deterministic run

Setup ends by writing `~/demo-ai-cdsp/run-plan.txt` — the exact steps the
pipeline replays every trip, in order: harvest with 3-run SHA-256 agreement,
extract with 3 readers + a cross-family judge, flag-don't-guess, sums in code,
fill Workday by visible labels, verify totals, and stop at
`awaiting your Submit`. Same steps, same order, every time — that's what makes
it repeatable instead of magical.

## Guardrails

Mail scope is read-only; the agent can fetch but never send, delete, or file
away. No stored credentials — SSO happens in your browser, Duo in your pocket,
the scripts hold nothing. Review is the design: unclear values are flagged
blank, and there is a hard stop before Submit. On your own desk this is fine;
as a departmental service, talk to IT and your Workday admins first.

## License

MIT — see [LICENSE](LICENSE). Filed, not feared.
