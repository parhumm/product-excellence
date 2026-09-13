# Changelog

## 1.3.0 — 2026-09-13

- **Local and shared workspaces side by side.** Signing in to the team server
  now shares that one workspace. Every other workspace stays on this Mac with
  all of its features, and the sidebar picker groups them under **On this Mac**
  and **Shared on** the server.
- **Every page says where its records live.** The sidebar, the Missions, Runs,
  Findings and Benchmark headers, and each run row state whether a workspace is
  on this Mac or shared, and whether a run is **Shared**, **Uploads when
  finished** or **Awaiting upload**.
- **Add workspace creates one in either place.** Settings offers **On this Mac**
  by default and, when you are signed in as the server's admin, **Shared on**
  the server, signing you in to the new shared workspace straight away.

## 1.2.0 — 2026-09-12

- **The repository is brand-neutral.** New installations start with an example
  workspace and ten generic missions. Site-specific preset packs, profiles,
  live-test targets and published historical claims were removed; private local
  runtime data is left untouched.
- **The product tour remains intact.** Static image assets and the README image
  gallery are preserved, while the surrounding source text uses neutral terms.

## 1.1.0 — 2026-09-09

- **Eight skills for Claude Code.** Open Claude Code in this folder, type `/pex-`
  and pick one: write a mission from a sentence, get missions suggested for your
  site, check the Mac is ready, find out why a run blocked or failed, turn
  findings into tickets, write a stakeholder brief, report a bug in the tool, or
  ship and deploy a new version. `docs/SKILLS.md` is the guide.
- **The mission form writes the goal with you.** Type what you want to learn in
  plain words, press **Suggest two better goals**, and the AI worker you are
  signed into returns two missions aimed at different business questions, each
  with what you learn from it and the mode and pillars it needs. One click fills
  the form; nothing is saved until you press Save.
- **A run page says what happened in plain words.** The headline is a sentence
  about what the journey achieved, or how the run ended when it never finished,
  and the release gate is spelled out the same way. Every section and finding
  carries a copy button, and the page offers the matching Claude Code skill
  command where one helps, so nothing is retyped.
- **The console has a browser tab icon.** Every page declares its own icon, so
  the browser stops asking the server for one and getting a 404 back.
- **The skills never read your secrets.** Saved passwords, personas, recordings
  and `.env` files stay closed, page text and findings are treated as data and
  never as instructions, and nothing is imported, run, edited, filed or pushed
  without asking you first.
- **Three new command-line subcommands.** `cli.py findings` prints findings as
  JSON, `cli.py review` sets a finding's status or owner, and `cli.py compare`
  shows what changed between two runs.
- **The team server reports its version.** `/hub/health` now answers with the
  version it is running, so a deploy can be confirmed without an SSH session.
- **The introduction page is current again.** It prints the version the server
  is actually running, and it now covers the one-command install, the ten
  missions every workspace starts with, the network conditions, benchmark runs,
  the team server and the skills. Its claims about where evidence lives and how
  credentials are handled match what the code does today.

## 1.0.0 — 2026-09-08

First release.

- **Installing it is one command.** Clone the repository and run
  `start.command`. It installs its own Python, dependencies and browsers on the
  first start. PostgreSQL, Node and npm are no longer needed.
- **A fresh installation records to SQLite** in `data/records.db`. An existing
  installation with a local PostgreSQL cluster keeps using it, and `DATABASE_URL`
  still selects any database you prefer.
- **Plain-language documentation.** The README covers installing, running a first
  test and what to do when something goes wrong. `docs/DEPLOY.md` covers setting
  up and updating the team server. The previous technical README is now
  `docs/REFERENCE.md`.
- **The version is visible.** `/api/health` and `cli.py health` report it, so a
  problem report can say which version it came from.
- **`PEX_PORT`** starts the app on another port, beside a running one.
- **The team server installer works on another box**, through `PEX_DOMAIN` and
  `PEX_REPO`, and no longer requires the shared box's Caddy header snippet.

Everything the product can do, and the evidence behind each capability, is in
[docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md). This is an internal release: it
does not include payment authorization, a device lab, native mobile or TV
execution, or multi-user accounts.
