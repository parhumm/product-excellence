# The narrative file

`build_report.py` takes every number, score, deduction, page address and
screenshot from the run's own record. This file carries only what the record
cannot: the sentence a person would say, the order the work should be done in,
and the reading of each screen.

Write it to the scratchpad as JSON, then pass it with `--narrative`.

```json
{
  "headline": "One sentence about what a visitor would experience. Not a score.",
  "improvements": [
    {
      "title": "Say what the product is on the first screen",
      "summary": "One line naming what is missing, for the ranked list.",
      "impact": "high",
      "confidence": "screenshot",
      "evidence": "step-000",
      "alt": "What the screenshot shows, for someone who cannot see it.",
      "saw": "What is actually on the screen: quoted text, controls, measured numbers.",
      "matters": "Why it costs the business something, in plain language.",
      "try": "One change worth testing. Say that the effect is a hypothesis."
    }
  ],
  "journey": [
    {
      "name": "Home",
      "evidence": "step-001",
      "alt": "What the screenshot shows.",
      "works": ["What already helps the visitor"],
      "improve": ["What gets in the way"]
    }
  ],
  "corrections": ["Where the run's own AI summary disagrees with its evidence."],
  "not_covered": ["What the mission deliberately skipped, so nobody assumes it passed."],
  "limits": ["Only if this run needs more than the three standard lines."]
}
```

## Rules the fields carry

- **impact** is `high`, `medium` or `low`: how close the problem sits to the
  decision the journey asked the visitor to make, and how many visitors meet it.
  It is your ranking, not a severity from the record; say so in the report.
- **confidence** is one of:
  - `confirmed`: a deterministic check, or an AI finding a critic confirmed;
  - `screenshot`: visible in the captured page, but not in the findings;
  - `unverified`: an AI finding a critic did not confirm, or your own reading.
- **evidence** must be an evidence id the run contains, such as `step-004`. The
  script refuses anything else, so a report can never cite a screen that was
  never captured.
- **saw** quotes the page. Prefer the exact words on screen and measured values
  from the record over paraphrase.
- **improvements** carries three to eight entries. An entry without `saw` appears
  in the ranked list only, which is the right shape for small polish items.

## What the script writes without you

Release gate, per-pillar scores with the deductions that produced them, a pillar
that was not evaluated marked "not scored", open findings by severity, blocked
mutating requests, duration, browser, viewport, network, locale, provider, model,
step and AI-call counts, the page address under each screen, and the three
standard "what this does not prove" lines.

Do not restate those numbers in the narrative; they are already on the page.

## Keep out

Never put a password, an email address, a token or a persona path in the
narrative. Name the artifact instead. The script redacts what it recognises, but
it cannot recognise everything.
