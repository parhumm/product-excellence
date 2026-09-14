# Android scenario steps

A scenario is an ordered list of steps a real tester would carry out on one device. It runs after the
app is installed and started. Keep it under 40 steps, and write the fewest that answer the question.

Every step is exactly one of these five, plus an optional `name` used only as a label.

- `goal: "…"` — one instruction the AI worker carries out on the screen. Optional `until: {text: "…"}`
  stops the goal early once that text appears. Reaching it proves navigation, nothing later.
- `check: {<one fact>, within: N}` — the fact has to become true once inside N seconds. Default 10.
- `hold: {<one fact>, for: N}` — the fact has to stay true across the whole N seconds.
- `event: {<one operation>}` — something done to the device rather than the app.
- `manual: "…"` — ask the person at the device to do something, with an optional `timeout` in seconds. Add `ask: "SMS code"` when the person should supply a value instead: the run page shows a field, and the console types the answer into the focused text field on the device (ASCII only, one field per step).
  (default 300). Recording stops while they work, so use it only for sign-in, payment and anything
  else the AI worker must not see or type.

## The facts a check or hold may state

Exactly one per step.

| Fact | Means |
| --- | --- |
| `text: "…"` | That text is readable on the app's own screen. |
| `text_absent: "…"` | That text is not on the app's own screen. Anchor the screen first with a goal. |
| `activity: {contains: "…"}` or `{equals: "…"}` | The focused package/activity matches. |
| `playing: true` or `false` | MediaSession reports playback, corroborated by position updates. |
| `notification: {text: "…", present: true}` | This package is showing a matching notification now. |
| `no_crash: true` | No fatal exception or ANR attributed to this package since the last goal or event. |

Three modifiers apply to any of them:

- `policy: unknown` when nobody has confirmed what the right behaviour is. The result is recorded as
  an observation: severity info, no score deduction, never release-blocking, and never required.
- `severity: P1 | P2 | P3 | info`, default P2, used when the fact is contradicted.
- `required: false` for a diagnostic check that should not stop the steps that follow. Confirmed facts
  are required by default; unknown-policy facts can never be required.

## The operations an event may perform

`network: wifi | cellular | offline | restore`, `speed: edge | gsm | umts | lte | full` with an optional
`delay_ms`, a standalone `delay_ms`, `wait: N`, `home: true`, `kill: true` (background, then let the
system reclaim the process), `relaunch: true` (force-stop and start again), `deep_link: "https://…"`,
and `open_notification: "…"` which opens the one notification this package posted with that text.

## What a scenario cannot prove

Say so in the mission rather than implying otherwise.

- Changing the transport is not changing a subscription, and not proof of zero-rating or entitlement.
- Emulator shaping is configuration evidence. It does not measure what the app actually transferred.
- Offline playback shows the download is usable over the seconds measured. It is not byte integrity.
- `pm clear` resets app data on the device. It is not a reinstall and it changes nothing server-side.
- An operator step is an attestation that a person did something, not a verified server state.

## Placeholders

Write `<Movie title>`, `<Search term>`, `<Account identifier>` and similar wherever a real value has to
be supplied. A mission cannot be saved while any `<…>` remains, which is what stops a template running
against the wrong content.
