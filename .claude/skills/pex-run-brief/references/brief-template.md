# <Mission name> · <website> · <date>

**Headline.** One sentence about what a customer would experience.

**Gate:** pass / warn / block, and the one reason for it.

## Scores

| Pillar | Score | Why |
| --- | --- | --- |
| Functionality |  |  |
| Conversion |  |  |
| Search and answers |  |  |
| UX and UI |  |  |
| Performance |  |  |

A pillar the run did not assess reads "not scored". That is not the same as
zero, and it is not averaged into anything.

## The three that matter

1. **<title>** · <severity> · <what it costs the business> · evidence
   `data/artifacts/<run id>/<file>`
2. ...
3. ...

Mark with "not confirmed" any finding an AI critic did not confirm.

## What to do next

1. ...
2. ...
3. ...

## What this does not prove

- One run, one browser, one network profile, one moment in time.
- A completed run means the test finished, not that the website is fine.
- Findings an AI critic has not confirmed are risks worth checking, not defects.

An Android run reads "one emulated device" for "one browser", says the app
rather than the website, and adds a fourth line: this is a disposable-emulator
lab result, not full accessibility, playback QoE, device-fleet or
field-performance certification.

## How this was tested

<browser>, <viewport>, <network profile>, <locale>, <provider and model>,
<number of steps>, <run id>.

For Android: <device and API>, <app version>, <network profile>, <locale>,
<provider and model>, <number of steps>, <run id>. The mission's `browser` and
`viewport` defaults never applied; leave them out.
