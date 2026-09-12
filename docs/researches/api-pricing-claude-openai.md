# API Pricing: Claude vs. OpenAI

*Prices in USD per 1 million tokens (MTok). Standard tier. As of September 2026.*

---

## Claude (Anthropic)

| Model | Input | Output | Cache read | Cache write |
|---|---|---|---|---|
| Fable 5.1 | $10.00 | $50.00 | $0.25 | $12.50 |
| Opus 5 | $5.00 | $25.00 | $0.50 | $6.25 |
| Sonnet 5 | $2.00 | $10.00 | $0.20 | $2.50 |
| Haiku 4.5 | $1.00 | $5.00 | $0.10 | $1.25 |

**Positioning**

- **Fable 5.1** — Next-generation intelligence for long-running agents
- **Opus 5** — Complex agentic coding and enterprise work
- **Sonnet 5** — High-performance model for coding and agents
- **Haiku 4.5** — Fastest, most cost-efficient model

---

## OpenAI

### Flagship models

OpenAI prices flagship models differently for short and long context.

#### Short context

| Model | Input | Cached input | Cache writes | Output |
|---|---|---|---|---|
| gpt-6-astra | $10.00 | $1.00 | $12.50 | $50.00 |
| gpt-5.6-sol | $4.00 | $0.40 | $5.00 | $20.00 |
| gpt-5.6-terra | $2.00 | $0.20 | $2.50 | $12.00 |
| gpt-5.6-luna | $0.20 | $0.02 | $0.25 | $1.20 |
| gpt-5.5 | $5.00 | $0.50 | – | $30.00 |
| gpt-5.5-pro | $30.00 | – | – | $180.00 |
| gpt-5.4 | $2.50 | $0.25 | – | $15.00 |
| gpt-5.4-pro | $30.00 | – | – | $180.00 |

#### Long context

| Model | Input | Cached input | Cache writes | Output |
|---|---|---|---|---|
| gpt-6-astra | $20.00 | $2.00 | $25.00 | $75.00 |
| gpt-5.6-sol | $8.00 | $0.80 | $10.00 | $30.00 |
| gpt-5.6-terra | $4.00 | $0.40 | $5.00 | $18.00 |
| gpt-5.6-luna | $0.40 | $0.04 | $0.50 | $1.80 |
| gpt-5.5 | $10.00 | $1.00 | – | $45.00 |
| gpt-5.5-pro | $60.00 | – | – | $270.00 |
| gpt-5.4 | $5.00 | $0.50 | – | $22.50 |
| gpt-5.4-pro | $60.00 | – | – | $270.00 |

### GPT-5 family (smaller and earlier versions)

| Model | Input | Cached input | Output |
|---|---|---|---|
| gpt-5.4-mini | $0.75 | $0.075 | $4.50 |
| gpt-5.4-nano | $0.20 | $0.02 | $1.25 |
| gpt-5.2 | $1.75 | $0.175 | $14.00 |
| gpt-5.2-pro | $21.00 | – | $168.00 |
| gpt-5.1 | $1.25 | $0.125 | $10.00 |
| gpt-5 | $1.25 | $0.125 | $10.00 |
| gpt-5-mini | $0.25 | $0.025 | $2.00 |
| gpt-5-nano | $0.05 | $0.005 | $0.40 |
| gpt-5-pro | $15.00 | – | $120.00 |

### GPT-4.1 and GPT-4o

| Model | Input | Cached input | Output |
|---|---|---|---|
| gpt-4.1 | $2.00 | $0.50 | $8.00 |
| gpt-4.1-mini | $0.40 | $0.10 | $1.60 |
| gpt-4.1-nano | $0.10 | $0.025 | $0.40 |
| gpt-4o | $2.50 | $1.25 | $10.00 |
| gpt-4o-mini | $0.15 | $0.075 | $0.60 |

### Reasoning models (o-series)

| Model | Input | Cached input | Output |
|---|---|---|---|
| o4-mini | $1.10 | $0.275 | $4.40 |
| o3 | $2.00 | $0.50 | $8.00 |
| o3-mini | $1.10 | $0.55 | $4.40 |
| o3-pro | $20.00 | – | $80.00 |
| o1 | $15.00 | $7.50 | $60.00 |
| o1-pro | $150.00 | – | $600.00 |

### Legacy models

| Model | Input | Cached input | Output |
|---|---|---|---|
| gpt-4o-2024-05-13 | $5.00 | – | $15.00 |
| gpt-4-turbo-2024-04-09 | $10.00 | – | $30.00 |
| gpt-4-0613 | $30.00 | – | $60.00 |
| gpt-3.5-turbo | $0.50 | – | $1.50 |
| gpt-3.5-turbo-0125 | $0.50 | – | $1.50 |
| gpt-3.5-turbo-1106 | $1.00 | – | $2.00 |
| gpt-3.5-turbo-instruct | $1.50 | – | $2.00 |
| davinci-002 | $2.00 | – | $2.00 |
| babbage-002 | $0.40 | – | $0.40 |

---

## Head-to-head at a glance

Comparable tiers, standard input/output (OpenAI short context):

| Tier | Claude | Input / Output | OpenAI | Input / Output |
|---|---|---|---|---|
| Frontier | Fable 5.1 | $10 / $50 | gpt-6-astra | $10 / $50 |
| High-end | Opus 5 | $5 / $25 | gpt-5.6-sol | $4 / $20 |
| Mid-range | Sonnet 5 | $2 / $10 | gpt-5.6-terra | $2 / $12 |
| Budget | Haiku 4.5 | $1 / $5 | gpt-5.6-luna | $0.20 / $1.20 |

**Notes**

- Claude and gpt-6-astra are priced identically at the frontier tier, including cache read ($0.25 vs. $1.00) and cache write ($12.50 for both).
- Claude's cache reads are consistently cheaper relative to base input (2.5–10% of input price) than OpenAI's (10% of input price on most models).
- OpenAI doubles input and raises output ~50% for long-context requests; Claude's listed prices do not vary by context length.
- OpenAI's "pro" variants (gpt-5.5-pro, gpt-5.4-pro) carry a 6× premium over their base models.
- OpenAI also offers Batch, Flex, and Fast mode tiers at different rates (not shown here).
