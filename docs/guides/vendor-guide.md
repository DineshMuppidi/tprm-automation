# Vendor Guide

For vendors completing a security assessment or working a remediation
finding through the TPRM portal.

## Signing in

You don't need a password. Go to the portal's login page, enter the email
address your risk contact registered for you, and click the link sent to
your inbox. **The link expires in 15 minutes** — if it's expired, just
request a new one; there's no limit on how many times you can do this.

## Completing an assessment

1. Your assigned assessments appear at `/assessments`. Each shows its
   status and how much of it you've completed.
2. Answer questions in any order — your progress saves automatically a
   moment after you stop typing (you'll see "Saving..." then "Saved").
   You can close the tab and come back later; nothing is lost.
3. Some questions only appear after you answer an earlier one a certain
   way (e.g. a follow-up about "additional environments" only shows up if
   you said you use them) — don't worry if a question you expected isn't
   there; it may not apply based on your other answers.
4. Questions marked **"Evidence required"** expect a supporting document —
   drag a file onto the upload area, or click it to browse. Screenshots,
   PDFs, and audit reports are all accepted.
5. Click **"Check my answer"** on any question to see how it's likely to
   be scored before you submit — this runs the same analysis the platform
   uses when you finally submit, so there are no surprises.
6. You can't submit until every visible question has an answer. Once you
   submit, you'll see your results immediately, including a downloadable
   PDF report.

**Be specific.** A vague answer ("we have good security") scores worse
than a specific one ("MFA is enforced via Okta for all admin accounts,
verified quarterly") — even if they mean the same thing to you. The
platform is looking for concrete, verifiable claims.

## Working a finding

If your assessment (or an automated monitoring check) identified a gap,
you'll see it at `/findings`.

1. **Acknowledge it** first — this starts the clock and lets your risk
   contact know you've seen it.
2. **Submit a remediation plan** — describe specifically what you'll do
   and by when. A plan that just says "we'll look into it" will be sent
   back asking for specifics; a plan with concrete steps and a date moves
   forward automatically.
3. **Upload evidence** once the fix is in place, then click **"Submit for
   validation."** The system checks whether the evidence actually
   supports what's required — for a high-severity finding, a screenshot
   showing one account isn't enough proof it's enforced everywhere; you
   may be asked to confirm scope or provide a fuller audit.
4. If evidence comes back requesting clarification, the specific ask is
   shown right there — respond to that exact question, not a resubmission
   of the same evidence.
5. **Can't fix it?** Use "Request an exception" — explain why, and what
   you're doing instead to reduce the risk in the meantime (compensating
   controls). Your risk contact reviews and approves or follows up.

Every message between you and the compliance team shows up in the
finding's message thread — questions, clarifications, and status updates
all in one place.
