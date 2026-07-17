# Demo prompts — the full text

The slides show each prompt **abridged**; this file is the appendix with the
full, working text. Each prompt became a skill:

| # | Prompt | Skill it became | Slide |
|---|--------|-----------------|-------|
| 1 | Harvest receipts from Gmail | `expense-trip-harvester` | 15–16 |
| 2 | Receipts → audited expenses.csv | `expense-trip-reconciler` | 26 |
| 3 | CSV → Workday draft (stop before Submit) | `workday-expense-report` | 30 |
| — | One-sentence orchestrator | `expense-trip-pipeline` | 34 |

---

## Prompt 1 · Harvest (→ `expense-trip-harvester`)

> Search my Gmail (read-only) from Feb 1 to May 31, 2026 for everything I spent
> on the ICSE 2026 Rio trip — flights, hotel, registration, meals, taxis, visa,
> baggage. Try receipt, invoice, e-ticket, confirmation, registration, payment,
> folio, and the Portuguese ones too: recibo, fatura, nota fiscal, comprovante,
> bilhete, reserva, pagamento. Dedupe by Message-ID.
>
> Do the whole search three separate times into ~/scratch/run1, run2, run3, and
> don't let any run peek at the others. For each email, make a folder named
> `<date>_<domain>_<msgid8>`: always save message.eml, and only save the
> attachments if the body doesn't already show the amount. That's just a yes/no
> check — don't read the number, don't add anything up.
>
> Then SHA-256 everything and promote only the files whose hash shows up in all
> three runs to ~/demo-ai-cdsp/expenses/, one copy each, same folder structure.
>
> Flag anything that isn't 3/3 and say which run missed it. Give me file counts
> per run and how many got promoted. No dollar amounts anywhere in the output.

## Prompt 2 · Reconcile (→ `expense-trip-reconciler`)

> Read every receipt in ~/demo-ai-cdsp/ — PDFs, photos, .eml — into
> expenses.csv: date, vendor, amount, currency, category, justification. Dates
> from the receipt, not the email. Three independent agents read each figure; a
> judge from another model family rules on every value. LLMs-as-judge:
> subagents retrieve each figure, master judge comments on every row. On
> disagreement, leave blank and flag — never guess. Convert BRL to USD at the
> rate on the day of the expense following guidelines. Consult these links:
>
> W&M Travel Regulations / Financial Operations travel policy — the rule that
> foreign-travel receipts must be translated to English with a historical
> exchange rate for the day of purchase attached to each receipt
> (travel-regulations, Travel Planning).
> https://www.wm.edu/offices/ce/policies/financial-operations/travel-regulations.php
> https://www.wm.edu/offices/financialoperations/travel/travelplanning/
>
> W&M Faculty Travel Tips — confirms itemized foreign receipts + proof of
> payment, each day's expense shown separately (faculty_travel_tips).
> https://www.wm.edu/as/_redirects/history/faculty/for_faculty/faculty_travel_tips/?q=as+history+faculty+for_faculty+faculty_travel_tips
>
> W&M Study Abroad financial resources — the "day of purchase" rate check,
> historically pointing to XE's converter (Financial Tips).
> https://www.wm.edu/offices/revescenter/geo/studyabroad/financingyourexperience/tips/
>
> All sums in code. Show me the full printlog.

## Prompt 3 · File in Workday (→ `workday-expense-report`)

> Fill my Workday expense report from ~/demo-ai-cdsp/expenses.csv, operating my
> own visible Chrome through the Claude-in-Chrome extension in my logged-in
> session — no headless, no separate profile. Open workday.wm.edu; when the SSO
> screen appears, log "waiting for Duo…" and do nothing until I approve Duo on
> my phone, then resume in the same tab. Create the expense report and fill one
> line per CSV row, targeting fields by their visible labels: DATE → Expense
> Date, CATEGORY → Expense Item, AMOUNT → Total Amount (USD), VENDOR +
> JUSTIFICATION → Memo, my NSF grant → Grant worktag (GR005334). Attach the
> matching receipt (pdf, png, or .eml) to each line. Recompute the CSV grand
> total and line count in code and compare to what the form shows; a
> blank/flagged amount fails the check. Then STOP — log "awaiting your Submit",
> leave the draft open, and hand me the mouse. Never click Submit.

## Orchestrator (→ `expense-trip-pipeline`)

> Compile my travel expenses for the ICSE trip to Rio, April 11–19, and file
> them to my NSF grant in Workday.

One sentence; Claude plans the run and calls harvester → reconciler →
workday-expense-report in order, then stops before Submit.
