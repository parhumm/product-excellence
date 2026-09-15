# Scenario steps

A scenario is an ordered list of steps a real tester would carry out in one sitting, on an Android
device or in a browser page. One vocabulary runs on both; the target decides which. It runs after the
app is installed and started, or after the site is opened. Keep it under 40 steps, and write the
fewest that answer the question.

Every step is exactly one of these five, plus an optional `name` used only as a label.

- `goal: "…"` — one instruction the AI worker carries out on the screen. Optional `until: {text: "…"}`
  stops the goal early once that text appears. Reaching it proves navigation, nothing later.
- `check: {<one fact>, within: N}` — the fact has to become true once inside N seconds. Default 10.
- `hold: {<one fact>, for: N}` — the fact has to stay true across the whole N seconds.
- `event: {<one operation>}` — something done to the device or the page rather than to the app.
- `manual: "…"` — ask the person running the mission to do something, with an optional `timeout` in
  seconds (default 300). Add `ask: "SMS code"` when they should supply a value instead: the run page
  shows a field, and the console types the answer into the focused text field (ASCII only, one field
  per step). On Android, recording stops while they work, so use it for sign-in, payment and anything
  else the AI worker must not see or type. On the web it means "do something outside the page —
  approve the request, revoke the entitlement, send the code — then continue". A `goal` step can also
  pause and ask for one value on its own when the app demands one, so no manual step is needed just
  to hand over a code.

## The facts a check or hold may state

Exactly one per step.

| Fact | On Android | On the web |
| --- | --- | --- |
| `text: "…"` | That text is readable on the app's own screen. | That text is readable in the page. |
| `text_absent: "…"` | That text is not on the app's own screen. Anchor the screen first with a goal. | Same, in the page. |
| `screen: {contains: "…"}` or `{equals: "…"}` | The focused package/activity matches. | The page address matches. |
| `playing: true` or `false` | MediaSession reports playback, corroborated by position updates. | The first `<video>`/`<audio>` element that has loaded anything reports it. |
| `notification: {text: "…", present: true}` | This package is showing a matching notification now. | The page created a matching notification through the Notification API. |
| `no_crash: true` | No fatal exception or ANR attributed to this package since the last goal or event. | No uncaught page error since the last goal or event. |

Three modifiers apply to any of them:

- `policy: unknown` when nobody has confirmed what the right behaviour is. The result is recorded as
  an observation: severity info, no score deduction, never release-blocking, and never required.
- `severity: P1 | P2 | P3 | info`, default P2, used when the fact is contradicted.
- `required: false` for a diagnostic check that should not stop the steps that follow. Confirmed facts
  are required by default; unknown-policy facts can never be required.

## The operations an event may perform

`network: wifi | cellular | offline | restore`, `speed: edge | gsm | umts | lte | full` with an optional
`delay_ms`, a standalone `delay_ms`, `wait: N`, `home: true`, `back: true`, `kill: true`,
`relaunch: true`, `deep_link: "https://…"`, and `open_notification: "…"` which opens the one
notification posted with that text.

On the web: `kill` drops the document to `about:blank` (in-memory state gone, cookies and storage
kept), `home` brings another tab in front so the page goes hidden, `relaunch` brings the page back and
reloads it, `back` is the browser's own back, and `deep_link` opens a URL on a host the mission is
allowed to visit. `speed`, `delay_ms` and `network: wifi | cellular` shape the browser and need
Chromium; `offline` and `restore` work in any browser.

## What a scenario cannot prove

Say so in the mission rather than implying otherwise.

- Changing the transport is not changing a subscription, and not proof of zero-rating or entitlement.
- Emulator shaping, and browser throttling, are configuration evidence. Neither measures what the app
  actually transferred.
- Offline playback shows the download is usable over the seconds measured. It is not byte integrity.
- `pm clear` resets app data on the device. It is not a reinstall and it changes nothing server-side.
- On the web, `kill` drops the document but keeps cookies and storage, so it tests in-memory state,
  not a cold start from nothing; and `no_crash` means no uncaught page error, not that nothing failed.
- An operator step is an attestation that a person did something, not a verified server state.

## Placeholders

Write `<Movie title>`, `<Search term>`, `<Account identifier>` and similar wherever a real value has to
be supplied. A mission cannot be saved while any `<…>` remains, which is what stops a template running
against the wrong content. The console lists every distinct placeholder as a blank above the step list
and disables the run button until each one is filled.

## Writing a journey others can fill in

A shipped journey is a scenario someone else picks from the gallery and runs in a minute.

- Two to four blanks, no more. Phrase each as an instruction to the person filling it in —
  `<Text shown only when signed in>`, not `<text>`. Every blank should contain a space.
- Use the same blank everywhere it means the same value; filling it once fills all of them.
- Say what the journey needs in `needs`: an operator to sign in, Chromium when run on a website.
- Carry no `platform`. The target decides it, and a journey that avoids `snapshot` runs on both.
