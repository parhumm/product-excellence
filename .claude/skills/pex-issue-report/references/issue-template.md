# Issue template

Title: the symptom first, then where. "Run stays queued forever after a browser
crash", not "Bug in runner".

```markdown
## What I did

1. ...
2. ...
3. ...

## What happened

...

## What I expected

...

## How often

Every time / once / intermittently, <n> of <m> attempts.

<!-- everything below comes from collect.py -->

## Environment

- Product Excellence <version>
- commit <sha> on <branch>
- macOS <version> on <arch>
- Python <version>

<details><summary>Health</summary> ... </details>

## The run

- id `<run id>`
- status <status>, outcome <mission_outcome>
- error: <error>
- mode, browser, viewport, network, provider

Last events:

- ...

<details><summary>data/app.log</summary> ... </details>
```

## Before filing

- Steps, expected versus actual, and the environment are all present.
- No password, token, cookie, email address or sign-in identifier survived.
- No screenshot or recording is attached; reference the artifact path instead.
- The behaviour is a defect in the tool, not a website finding and not the
  read-only policy refusing something on purpose.
