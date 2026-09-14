# Changelog

## Unreleased

- **A run can ask you for a value instead of giving up.** When a web run or an
  Android journey reaches a field it has no value for (a phone number, email,
  username, password, one-time code, authenticator code or card details), it
  pauses and the run page asks for that value, with **Skip** and **Stop run**
  next to it. The value is filled into the field, masked in screenshots and
  scrubbed from the saved evidence, and never stored in the run.
- **Android missions can carry an ordered scenario.** Up to 40 steps on one
  device: goals for the AI worker, checks that a fact becomes true, holds that a
  fact stays true, events done to the device, and manual steps handed to the
  person sitting at it. A mission without a scenario runs exactly as before.
- **Five shipped journeys** cover the questions that need state: playback across
  a transport switch, a download over a weak link with pauses, downloads and
  search history per account, a notification opened much later, and a shared
  link opened while signed out. Each leaves placeholders where a real title or
  account belongs, and refuses to save while one is left.
- **A guided builder, and the same steps as YAML.** Ordered rows with native
  controls for every step kind, event and fact; move, duplicate and remove from
  the keyboard; a budget line that offers to raise the limit when the waits need
  more time. The advanced view spells the same steps as text, and text that does
  not parse stays in the editor instead of replacing working rows.
- **Draft the steps from a sentence.** The signed-in AI worker writes a first
  scenario, validated against the same schema the form uses. Nothing is replaced
  until you say so, and drafting never touches the device.
- **Manual steps without recording credentials.** Recording is stopped and
  confirmed stopped before the operator notice appears. The run page shows the
  instruction, the paused recording, the real remaining time and a Continue
  control; the recording resumes afterwards and the gap is reported.
- **The run page shows the scenario.** A numbered progress strip and a step
  table, each step reporting a word and its evidence rather than a colour.
  Measurements that were not available and questions about intended behaviour
  are listed apart from the defects, and a refresh no longer takes the control
  out from under you.
- **Evidence that cannot be read is never read as a failure.** An unreachable
  screen, an unknown foreground package or a parser error makes a step
  unavailable: a coverage gap, not a defect.
- **Unconfirmed behaviour is a question, not a defect.** A check marked
  `policy: unknown` is recorded as an observation with severity info. It deducts
  nothing and blocks nothing.
- **Start state is explicit.** Fresh app data, keep what the last run left, or
  load a device state saved on this Mac. Saved states live under Settings →
  Android device: never overwritten, validated against what is on disk before
  they load, and refused while a run owns the device.
- **Comparison says what it can establish.** Matching conditions and the right to
  call a finding reproduced are answered separately, with the actual reason when
  a reproduction cannot be claimed: a different build, a start state that was
  inherited rather than established, an operator attestation, or a required step
  left without evidence.

## 1.5.2 — 2026-09-14

- **New demo videos.** The landing page and the README now show five
  demonstrations covering websites and Android apps: an introduction, Android
  app QA with an APK, benchmarks with network conditions and release
  comparison, a competitor benchmark, and a full video player test.
- **The site says what the tool tests.** The page title, description and
  opening paragraph name Android app testing beside website testing.
- **Research notes** on stateful product QA and on Android failure discovery
  are included in the repository.

## 1.5.1 — 2026-09-13

- **Add an Android app in one step.** Settings → Websites and Android apps takes
  the app name and its APK together, and the mission form points there.
- **Every workspace website is a target.** Missions bound to the default web
  target no longer fail when the workspace lists no allowed domains; the
  seeded workspace gets its target on first start.
- **Android journeys reach their goal.** Taps are no longer refused on API 34,
  a control that moved inside a carousel or shares its bounds with a Compose
  child is still tapped, the model is told how to read unlabeled native
  controls and may not give up before trying one, and Android's full-screen
  hint is confirmed before the run so video players are not hidden.
- **Run pages update live.** Android runs log the launch, every screen and
  every action as they happen, so the execution log and journey timeline fill
  in during the run.
- **APK inspection** accepts launchers declared as activity-alias and
  minSdkVersion badging; the dynamic model is resolved before the AI CLI is
  called; the designated AVD guard fails closed when none is set.

## 1.5.0 — 2026-09-13

- Workspaces now contain explicit website and Android targets. APK builds are
  validated, content-addressed on each execution Mac, pinned into queued runs,
  and compared without rewriting historical web records.
- Missions and finished runs can remain local inside a shared workspace, then
  be shared explicitly with dependency and artifact verification.
- A designated disposable AVD can run bounded native audits and journeys with
  screenshots, MP4 recording, package-attributed crash/ANR logs, launch and
  memory measurements, and explicit missing-capability coverage.
- Team workspaces that use 1.5 features require a compatible console through a
  numeric protocol-version gate. The read-only team UI remains available.

## 1.4.0 — 2026-09-13

- **Continue a run where its budget ended.** A journey that ran out of AI calls
  or steps no longer has to be replayed from the start. **Continue** carries the
  same run on under its own id: it reopens the last page with the cookies that
  visit saved, numbers the next actions from where they stopped, and adds to the
  findings already on record. A run that only lacked its evaluation runs the
  evaluation alone. Continuing is refused, with a reason, for a run that is
  queued or running, shared on a team server, a benchmark, one that captured no
  page, or one already at the highest limits its mission allows.
- **A run that stops at its budget still gets its review.** The pillar review is
  now worth one AI call past the budget, so the summary, the scores and the AI
  findings are there to read instead of waiting for a continuation. Findings no
  critic could challenge stay marked unconfirmed and count half.
- **A continued run shows every visit.** The timeline marks where the browser
  reopened, the run header says how many visits there were, and the recording
  and browser trace of every part stay on the run page and in the Markdown
  export, which now lists them and says the report covers each visit.
- **A slow page gets time to load.** Every page in a journey now has the same
  45-second navigation budget the first one had, so an origin that takes tens of
  seconds to paint no longer ends the run. A screenshot that does not finish is
  recorded on that observation and the page text, metrics and accessibility pass
  are kept.
- **Goal suggestions answer faster.** The mission form's suggestion call gives up
  after a minute instead of leaving the button waiting on a stuck worker.

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
