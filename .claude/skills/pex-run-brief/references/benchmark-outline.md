# The benchmark narrative

A benchmark report answers one question for a product team: for each thing we
should fix, who already does it well, and what exactly should we copy? It is
built from one or more benchmark runs, usually one per page type (home, detail
page, plans), because a benchmark review sees only the last screen of each site.

`build_report.py` takes every rank, site outcome, metric, page address and
screenshot from the runs. This file carries the cards. Write it to the
scratchpad as JSON and pass every run id with it:

```bash
.venv/bin/python .claude/skills/pex-run-brief/scripts/build_report.py <run> <run> <run> \
  --narrative <scratchpad>/benchmark.json --out <path>.html
```

`docs/examples/benchmark-report-sample.html` shows the result for two
fictional runs with drawn screens.

```json
{
  "title": "Northwind TV Signup Benchmark",
  "headline": "One or two sentences: where the product stands and what kind of fixes the competitors show.",
  "pages": {
    "0a1b2c3d": {
      "label": "Home page · first screen",
      "question": "Does a stranger quickly understand what it is, what it costs and how to start?",
      "names": {"northwind.example": "Northwind", "alpha.example": "Alpha"}
    }
  },
  "plays": [
    {
      "title": "Say what the product is on the first screen",
      "impact": "high",
      "confidence": "screenshot",
      "copy_from": "Alpha",
      "screens": [
        {
          "run": "0a1b2c3d",
          "evidence": "step-001",
          "who": "Northwind · home",
          "caption": "No headline, price or free offer.",
          "alt": "What the screenshot shows, for someone who cannot see it.",
          "marks": [{"x": 2, "y": 11, "w": 96, "h": 4.5, "label": "First heading: a poster row", "below": true}]
        }
      ],
      "code": [
        {"run": "0a1b2c3d", "evidence": "step-001", "side": "today", "who": "Northwind",
         "lines": ["<meta name=\"robots\" content=\"noindex nofollow\">"]}
      ],
      "speed": false,
      "today": "What the product does now, quoting the page.",
      "best": ["Alpha: the competitor's own words, quoted, with a translation in brackets if needed."],
      "do": ["One concrete change, with suggested wording where it helps."]
    }
  ],
  "also_found": [
    {"what": "An issue outside the planned questions", "where": "Plans page",
     "basis": "Automated accessibility check", "confidence": "confirmed", "run": "0a1b2c3d", "evidence": "step-000"}
  ],
  "keep": ["Where the product already leads, so nobody removes it by accident."],
  "corrections": ["Where a run's own AI summary disagrees with its screenshots."],
  "limits": ["Only what the standard limits do not already say."]
}
```

## Rules the fields carry

- **pages** is keyed by run id or its first eight characters. `label` and
  `question` head that run's ranking card; `names` turns hosts into brand names
  wherever the report shows a site.
- **plays** are the cards, three to eight, in the order a team should work.
  Keep the numbering of an earlier journey report when one exists, so the two
  documents can be read together.
- **screens** are whole screenshots. The script never crops, zooms or retouches
  them; show a different evidence id instead of cutting one down. Put the
  product's own screen first, then the competitor screens that show the fix.
- **marks** outline the element a card talks about: `x`, `y`, `w` and `h` are
  percentages of the whole screenshot. Look at the image before placing one. A
  label sits above its box; set `below` when the box is near the top, and
  `dashed` for "below this edge" or "missing here". The script anchors the label
  on whichever side of the box has more room and wraps it there, so it never
  runs off the screenshot; set `right` to `true` or `false` only to override that.
  One to three marks per screen.
- **code** is for what a screenshot cannot show, such as robots directives,
  titles and structured data. Every line must be copied from that screen's
  `step-NNN.dom.txt`; the script refuses a line it cannot find there. Use
  `"side": "today"` for the product's own source.
- **speed**: on the card about load time, `true` draws the speed table for
  every run inside that card, and a run id draws only that page's rows. Runs no
  card charts get their own speed section.
- **confidence** is `confirmed` (a deterministic check, or the page source),
  `screenshot` (visible on a captured screen) or `unverified` (read from page
  text only, or your own reading).
- **today**, **best** and **do** quote the pages. A competitor claim that no
  screenshot shows, for example because a cookie banner covered it, says so.
  Suggested wording names only terms the product actually offers; if you do not
  know, say who has to confirm it.

## What the script writes without you

Each run's ranking with the product highlighted and unanswered sites struck
through, each run's release check and pillar scores ("not scored" where a
pillar was not assessed), the speed table from each site's measured LCP and server response,
the sites that did not answer and what they showed, the header facts, the AI
call count, the masked-field note and the standard limits.

## Check before building

- Read every screenshot you cite. A run summary can call a page empty when a
  cookie banner hid it, or miss content that is plainly on screen.
- Prices, dates and counts can change between runs. When you combine runs from
  different days, say which screen shows which day.
- Never put a password, an email address, a token or a persona path in the
  narrative.
