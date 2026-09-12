# Mission fields and goal voice

## Modes

| Mode | Use it for | Typical budget |
| --- | --- | --- |
| `audit` | one page judged without carrying out a task | `ai_budget` 6, `max_seconds` 600 |
| `journey` | a task a customer performs, start to stop | `max_steps` 10, `ai_budget` 14, `max_seconds` 900 |
| `explore` | working out what the product does, then using it | `max_steps` 14, `ai_budget` 20, `max_seconds` 1200 |
| `benchmark` | the same question on this site and each competitor | `max_steps` 5 per site, `ai_budget` 30, `max_seconds` 2400 |

A journey, explore or benchmark mission needs an AI worker; `provider: none`
suits an audit that only measures.

## Fields (`engine/contracts.py`, class `Mission`)

| Field | Notes |
| --- | --- |
| `project_id` | the workspace id from `cli.py missions` |
| `name` | short; "Subject · what it does" reads well |
| `url` | http or https, no credentials inside it |
| `goal` | 5 to 4000 characters, the voice below |
| `success_text` | text that proves success; leave empty unless it is exact |
| `allowed_domains` | the workspace's own domains, nothing else |
| `mode` | journey, explore, audit or benchmark |
| `competitors` | benchmark only, up to 10 start URLs |
| `browser` | chromium, firefox or webkit |
| `viewport` | desktop, mobile or tablet |
| `network` | baseline, slow-mobile, poor-mobile, offline, and the rest from `cli.py health` |
| `provider` | codex, claude, auto or none |
| `model`, `model_max`, `effort` | leave at the defaults unless the user asks |
| `max_steps` | 1 to 40 |
| `max_seconds` | 30 to 3600 |
| `ai_budget` | 0 to 60 AI calls |
| `locale` | fa-IR by default |
| `login_identifier`, `login_password` | credentials; the goal uses the placeholder |
| `persona_id` | a saved test session from `scripts/capture-persona.py` |
| `pillars` | functionality, cro, seo_aeo, ux_ui, performance |

## Three goals to imitate

Audit, five pillars:

> Review this home page as a first-time visitor. Judge what the business offers
> and who it is for, how clear the main call to action is, which trust signals
> are present, the page title, description and headings, keyboard and contrast
> accessibility, and how quickly the page becomes usable. Report anything that
> would make a visitor leave.

Journey that must stop before submitting:

> Find how a new customer creates an account and open the sign-up form. Record
> which fields are required, whether a phone number, email or another service is
> needed, and what the form says about verification, price or terms. Type one
> obviously invalid value into a plain text field to see the validation message.
> Do not submit the form and do not create an account.

Journey that may sign in (the placeholder is written literally in the goal):

> Find the sign-in entry and open it. If this mission has sign-in credentials
> saved, sign in and confirm the account area opens; type {{password}} into the
> password field and the engine fills the stored secret for you. Without
> credentials, inspect the form only, then stop. Sign-in that needs a one-time
> code sent by message cannot be completed; report that as the outcome.

## File shape

```yaml
name: Pricing · renewal terms before payment
url: https://example.com/pricing
goal: |
  Find the prices or plans and read what a customer is told before paying.
  Judge whether the price, currency, billing period, renewal and refund terms
  are clear. Do not enter payment details and do not buy anything.
allowed_domains:
- example.com
- www.example.com
mode: journey
provider: auto
browser: chromium
viewport: desktop
network: baseline
max_steps: 10
max_seconds: 900
ai_budget: 14
locale: fa-IR
pillars:
- functionality
- cro
- ux_ui
```
