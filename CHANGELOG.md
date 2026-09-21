# Changelog

## 1.8.0 — 2026-09-21

- **A run page can write its own shareable report.** **Export HTML** on a
  finished run produces the standalone page `/pex-run-brief` used to be needed
  for: the screens the visitor saw, ranked improvements, scores and what the run
  does not prove, with the screenshots inside the file so it opens offline. Pick
  the AI worker, the model and the Codex account there, as a mission does; one
  call writes the reading, and every number on the page still comes from the
  run's own record. The wait is counted on screen — a long run's evidence can
  take a worker minutes to read — and the finished report is offered as a link
  to open or to save, rather than appearing in the downloads folder. An improvement that cites a screen the run never captured is
  dropped rather than shown. The reading is kept beside the evidence, so a second
  export costs nothing while the scores stay current; a different model, or
  `cli.py report ID --refresh`, writes a new one. The skill stays for the reports
  the button does not write: a benchmark playbook, or a narrative you want to
  steer. The Markdown download is unchanged, now labelled **Export Markdown**.
- **A reading outlives the browser that asked for it.** A three-minute call used
  to die with the connection when Chrome suspended its sockets: the page said
  "Failed to fetch", and a retry paid for the same reading again. The call now
  runs on its own and saves the narrative as soon as it has one, so a laptop
  that sleeps mid-read costs the wait and not the call. A second click on the
  same run and choice waits on that reading rather than starting another, a
  dropped connection is answered with what to do about it, and a worker that
  stops answering ends after ten minutes with a reason instead of a stack trace.
- **Missions saved before 1.6 reach the team server again.** 1.6 renamed the
  oracle from `activity` to `screen` but left every saved mission, version and
  run naming the old field, so the team server refused them as invalid records.
  The app now renames it inside a check or hold once, when it starts, after
  writing a backup. What a sample saw in front keeps its name, as does a
  target's `launch_activity`.
- **An added import survives an interruption and carries its versions.** An
  apply cut short could leave a run on the server with its manifest entry still
  open; the next pass now closes the entry instead of stalling on it. A
  mission's versions travel with it, or join it when it is already there, but
  never land on a team mission reused by name.

## 1.7.0 — 2026-09-19

- **A benchmark now produces a playbook, not a scoreboard.** `pex-run-brief`
  takes several benchmark runs, one per page type, and builds a report that puts
  each problem beside the competitor screenshot showing the fix, with the element
  outlined, along with each run's ranking, the measured speed of each page and
  the sites that did not answer. Every number, score, deduction and address still
  comes from the run's own record, and a narrative is refused when it cites a
  screen the run never captured, a mark outside its screenshot, or a code excerpt
  that is not in the saved page source. The one-page Markdown brief stays beside
  it: the brief to paste into a ticket, the report to send to someone.
- **A report states the conditions the run actually had.** An Android mission
  still carries the web defaults `browser: chromium` and `viewport: desktop`, and
  they never applied to the emulator. The report now reads target, app, device
  and `network_applied` instead, reports launch time, jank and PSS only where the
  emulator measured them, names the package under test rather than an empty chip,
  drops a condition with no recorded value, and says "the app", not "the
  website", in an Android run's limitations.
- **Reports open anywhere, without the network.** Neither builder loads fonts
  from Google and screenshots are embedded, so a report about a private site
  opens with its evidence offline.
- **Benchmark reports read on a phone.** A mark's label anchors on the side of
  its box with more room and wraps there, so it no longer runs off the screenshot
  or the page; `right` still overrides. Each ranking card shows the run's release
  check, overall score and every pillar, with "not scored" where a pillar was not
  assessed. `speed` can name one run, so a speed card charts only that page, and
  runs no card charts keep their own speed section. A site that did not answer is
  described up to a sentence or word, never cut mid-word.
- **The score table no longer contradicts itself.** Open findings are counted the
  way `engine/outcomes.py:actionable` counts them, so a rejected or closed
  finding no longer argues with the score. The three standard limits always
  survive; a narrative's own limits are added to them rather than replacing them.
  An evidence id whose screenshot is missing is refused, matching `benchmark.py`.

## 1.6.0 — 2026-09-15

- **The landing page describes journeys, one-sentence missions, operator-assisted
  runs, routes and network profiles.**
- **A journey can change the way out mid-run.** A scenario step names a saved
  proxy route, or `direct`, and the connections that follow leave that way. The
  run owns a relay on its own machine and the browser or the emulator is pointed
  at it once, so the route behind it changes without a new session: the
  connections opened on the previous route are dropped, the new exit address is
  probed and recorded, and a route that cannot be established stops the run
  instead of quietly going out directly. A route may carry the link speed it is to
  be measured under. Upstream credentials stay in the relay and reach neither the
  page, the device nor the record.
  Only HTTP(S) upstreams can be switched to. What this establishes is the exit
  address per switch, nothing about country, ISP or carrier: DNS is resolved on
  this machine and UDP/QUIC is never proxied. Every browser engine and the
  emulator were accepted live against two tagged upstreams, each one's own
  request read back on the route that carried it; the transcripts are kept in
  `artifacts/route-live/`.
- **An Android journey can take a route too.** The emulator is launched against
  the run's relay with `-http-proxy`, so nothing in the guest holds a proxy
  setting and no app can opt out of it. The designated AVD must not already be
  running: one that is was never launched against this relay, and the run says so
  before touching a single setting on it.
- **An Android mission can name a network profile.** Its latency and bandwidth are
  applied through the emulator console, which the transport gate measured to
  change traffic on the mobile radio only — so a profile that shapes takes the
  device to mobile data first, and shaping asked for over Wi-Fi is refused rather
  than reported as applied. The profile is the condition the run is measured
  under, not a fault in it; a `network: restore` step goes back to it, and the end
  of the run goes back to the device's own settings. Offline, jitter, loss,
  reordering and periodic disconnects were never measured there and are refused.
  The full transport gate transcript is kept in `artifacts/android-gate/`.

- **A mission starts from one sentence.** The new mission form opens on *What do
  you want to find out?*. Write it in your own words and four whole missions come
  back as cards, in two groups: two the worker works out for itself from the goal
  alone, and two scenarios with every step already written, in order and in plain
  words. Each card says what it would change — Chromium for a shaped link, a person
  at the screen for a manual step, an Android target for an app event — and what
  has to exist first.
  **Use this goal** or **Use this scenario** fills in the name, goal, mode, pillars
  and steps, and raises the time and action budgets if the steps need the room.
  Nothing is saved and nothing runs until you press **Save mission** or **Save and
  run**.
- **A mission the worker gets wrong no longer costs the whole answer.** One
  suggestion that does not fit the contract is dropped and named underneath the
  cards that survived, instead of failing the minute you waited for.
- **Change a mission by describing the change.** **Change something** takes a
  sentence such as "add a relaunch before the last check" and returns the whole
  mission changed, as one card you apply the same way. **Undo**, beside the
  mission heading, puts back the name, goal, steps, mode, pillars, browser and
  budgets exactly as they were before the last thing the worker filled in.
- **Steps read as a list before they read as a form.** The **Steps** section shows
  the scenario as numbered sentences; **Edit steps** opens the rows and closes them
  again. Shipped journeys, the sentence drafter and the YAML editor moved under
  **Other ways to get steps**, and all four spellings stay the same steps.
- **A manual step can name the value it needs**, such as a one-time code, in its
  own field. The name is saved; the value never is.
- **Write it yourself** opens the same empty form, so every manual tool and every
  saved setting stays reachable with no AI worker signed in.

- **A run can ask you which way to sign in.** A screen that offers a password, a
  code by SMS, a code by a call and a Google account is asking which way in, not
  for a secret. Web runs and Android journeys now pause with those options as
  buttons on the run page; you pick one and the run clicks or taps it and carries
  on. **Skip** and **Stop run** stay beside them.
- **A run can ask you for a value instead of giving up.** When a web run or an
  Android journey reaches a field it has no value for (a phone number, email,
  username, password, one-time code, authenticator code or card details), it
  pauses and the run page asks for that value, with **Skip** and **Stop run**
  next to it. The value is filled into the field, masked in screenshots and
  scrubbed from the saved evidence, and never stored in the run.
- **Missions can carry an ordered scenario, on Android and on the web.** Up to 40
  steps on one device or in one browser page: goals for the AI worker, checks
  that a fact becomes true, holds that a fact stays true, events done to the
  device or the page, and manual steps handed to the person sitting at it. One
  vocabulary and one interpreter serve both platforms; the target decides what a
  step acts on. A mission without a scenario runs exactly as before. Two things
  differ on the web: link shaping needs Chromium, and a saved device state cannot
  be loaded, because a website mission carries its session through a persona.
- **Twelve shipped journeys**, none of them tied to a platform, cover the
  questions that need state: playback across a transport switch or a dropped
  connection, a download over a weak link with pauses, downloads and search
  history per account, a notification opened much later, a shared link opened
  while signed out, a session and a filter across a restart, sign-out that really
  signs out, back after a search, a form rejecting bad input, and checkout up to
  payment on a slow link.
- **A journey gallery, and fill in the blanks.** **Missions → Start from a
  journey** searches the twelve by name, description and tag, says what each one
  needs, and opens the mission form with the target, name, goal, time limit and
  steps already set. Every blank a journey leaves is listed above the steps with
  its own labelled field; filling one fills every occurrence across the name, the
  goal and the steps. The run button says how many are left and stays disabled
  until none are, and the server still refuses a mission that holds one.
- **`screen` replaces `activity`** as the fact for where the app is: the focused
  activity on Android, the page address on the web. **A new `back` event** goes
  back on either platform. Drafting works from the goal when no sentence is
  given, and the time limit fits itself to the waits a journey commits to.
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
