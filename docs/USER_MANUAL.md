# Product Excellence
### A short, practical user guide

## What is it?

Product Excellence is a private website and Android app testing assistant that runs on your computer.

Give it a page to review or a task to try, such as “find a movie and open its details.” It opens a browser, checks what happens, and saves screenshots, a recording, and findings for you to review.

Starter missions are included. You can also create your own missions.

## Why use it?

It helps you:

- Find problems before customers report them.
- Check the same experience across browsers, screen sizes, and connection speeds.
- Give your team evidence alongside a problem report.
- Repeat a test after a change and compare the results.

It saves investigation time. A person still needs to decide which findings matter.

## What can it check?

| Area | What you can learn |
|---|---|
| Functionality | Whether pages and browser actions work, and where errors appear |
| Ease of use | Possible confusing layouts, unclear controls, and accessibility problems |
| Conversion opportunities | Ideas that may help people complete a task |
| Search visibility | Missing page information and possible indexing problems |
| Speed and video | How a page loads and how video behaves when playback is available |
| Competitors | How your website answers a question compared with the competitors you list |

You can also save reusable missions, schedule repeat checks, assign findings, and download reports.

**AI suggestions are opinions supported by evidence, not proven business results.** The service does not measure conversion improvement.

## How to use it

### 1. Open the service

Visit [Product Excellence](http://127.0.0.1:8741).

If it is stopped, double-click **start.command** in the project folder. Leave its terminal window open. If it is not installed on this computer yet, follow [the README](../README.md).

Open **Settings** to check whether the browsers and your AI subscription are ready.

### 2. Choose the workspace and target

The **Workspace** selector chooses the product you are working on. A workspace can contain several website and Android targets. Missions, runs, findings, comparisons and scheduled checks stay inside it. Choose the target on each new mission.

Each workspace website is listed under **Settings → Websites and Android apps** as a target; its URL and allowed domains come from the workspace. Add another website there: a name, its address, and the domains a test may visit.

For an Android app, open **Settings → Websites and Android apps**, choose **Android app**, give it a name and pick the APK file in the same form. The first APK sets the package name; later builds are added with **Add APK build** on the app's row. New runs use the latest non-archived build or pin an exact SHA. The mission form's Target field links back here when the workspace has no app yet. The disposable AVD is cleared only for that package before each run; Android sign-in, benchmark, SEO/AEO, proxy and network matrices are unavailable.

### 3. Choose a mission

Open **Missions**. Every workspace already contains ten missions you can run as they are:

home page audit; register; sign in; search; core features; pricing and checkout; get the app; SEO and AEO; UX, UI and accessibility; and the same task on a slow phone.

Missions that need an account refuse to start until you give them one. Open the mission and fill in the sign-in identifier and password, or, where the website signs in with a code sent by message, capture a signed-in browser session instead:

```
.venv/bin/python scripts/capture-persona.py --url https://example.com
```

For anything the presets do not cover, you do not have to fill in the mission form yourself. Open Claude Code in this folder and type `/pex-mission-write` with a plain sentence about what to check, or `/pex-mission-suggest` to see what is worth testing on your website. Both show you the mission before creating it. See the [skills guide](SKILLS.md).

Import the saved file under **Settings → Test personas**, then choose it on the mission. A mission you delete is not created again.

You can also create your own.

Start with a small, clear task:

> Open the homepage, find search, and open a movie’s details.

Choose:

- **Page / pillar audit** to review a page.
- **Journey** to attempt a specific task.
- **Explore** for less directed browsing.
- **Benchmark** to answer the same question here and on each competitor, then compare them.

A benchmark mission carries a list of **competitor start URLs**, one per line. The run pursues the goal on your own website first and then on each competitor, and each site gets its own outcome, screenshot and measurements. The finished run opens with a comparison table — outcome, rank, load time, layout shift and accessibility violations per site — followed by what the review found strong and weak on each. A competitor that refuses to load is reported as blocked for that site; the rest of the comparison continues. **Benchmark** in the sidebar lists these missions and their runs.

Findings stay about your own website. A competitor's defects are not your work, so they appear in the comparison text and never as a finding you have to close.

Select the browser, screen size, connection, and AI worker. **No AI** runs automated checks without AI judgment.

### Choose a Codex account

The standard account is the login in `~/.codex`. If you keep additional signed-in
profiles in directories such as `~/.codex-work` and `~/.codex-personal`, the
local console discovers profiles containing `auth.json` and lists their names
and cached email labels. Credentials stay in those directories.

In **Settings → Workspaces (websites)**, choose **Default Codex account** for a
workspace. In a mission, **Codex account → Workspace default** inherits that
choice; selecting a named account overrides it for that mission. Selecting
**Default** explicitly uses the standard profile. Without either choice, runs
use `~/.codex`. These choices apply when the worker is Codex or First available
worker; they do not change Claude's login.

The account is resolved when a run is queued and recorded in its snapshot and
run details. A new replay resolves the mission choice and current workspace
default again. Named profiles must exist on the machine executing the run;
sharing a mission does not transfer its credentials. Automatic discovery of
additional profiles currently requires file-based `auth.json` caches.

An inherited `CODEX_HOME` from the app that launched the service does not select
the worker account. Administrators can set `PEX_CODEX_HOME` before startup to
override the standard profile's location. A cached login or email label does
not establish available credits: the provider can still reject a run. Account
switching does not refill a workspace or repair Codex's local session database.

### Choose a model

Then pick the **AI model**. The list shows the models each worker accepts with an
estimated price beside each one, so a cheaper or faster model can be chosen for
routine runs and a stronger one kept for important ones. **CLI default** uses
whatever the Codex or Claude command line is configured to use. **Custom model
id** accepts any other id the worker accepts.

**Dynamic** is the choice a new mission starts with, balancing quality, cost
and speed. A run asks the AI for several different things, and they do not need the
same model. Reading a page and choosing the next click is routine work, so
Dynamic gives it the smallest model on the list. Judging whether the goal was met
and challenging a finding get the next model up. The review that reads all the
evidence and writes the findings uses Opus 5 / GPT-5.6 Sol at high effort,
capped by your allowance. P1 finding critics escalate to Opus/Sol at medium
effort, also within the ceiling; other critics use Sonnet/Terra at low effort.
Fable/Astra remain available as fixed models for the hardest work; a frontier
ceiling does not force routine reviews onto them.

That allowance is **Highest model allowed**. Set it to the strongest model this
mission may ever use; left empty it means the strongest model the console lists.
Nothing in the run goes above it. Reasoning effort is chosen per call too, so the
effort control is hidden while Dynamic is selected.

If a cheap model gets stuck, Dynamic notices. When an action is refused by the
safety policy, or the page does not change after it, the next action is planned
one model and one effort higher, and it keeps climbing until the ceiling. When a
run set to **First available worker** has to switch to the other worker, the
ceiling moves with it: the Codex and Claude lists are matched tier for tier, so
an allowance of Claude Opus 5 becomes GPT-5.6 Sol rather than the top model.

Choose a full model id rather than a short nickname. Probing the Claude command
line on 6 September 2026 showed that `sonnet` was answered by Claude Opus 5 and
`opus` by Claude Fable 5.1, while every full id answered as itself. The list
therefore offers only full ids, and every run records the model that actually
replied, not the one that was asked for. The Claude picker offers Fable 5.1,
Opus 5, Sonnet 5 and Haiku 4.5. Legacy ids remain usable via Custom model id
and retain their prices. Saved custom ceilings remain selectable; an unlisted
ceiling becomes the review tier.

### Token use and cost estimates

Every run records each AI call. You can see them in three places:

- The **runs** table shows the models used, total tokens and the estimate.
- The **AI usage** section of a run lists every call: purpose, the model that
  replied, effort, input, cached, output tokens, duration and estimate.
- The Markdown report contains the same table, and `scripts/cli.py models`
  prints the catalogue with prices.

*Input* counts fresh prompt tokens plus tokens written to the prompt cache.
*Cached* counts cache hits, which are much cheaper. A count that the worker did
not report is shown as `—`; it is never shown as zero.

**Prices are estimates only.** Runs go through your Codex or Claude
subscription. Nothing here is billed per call, and no API key is used. The
estimate applies published standard API prices to the tokens the worker reports, so
that two runs, two models or two phases can be compared with each other. Prices
published 7 September 2026, per million tokens:

| Model | Input | Cached | Cache write 5m | Cache write 1h | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Astra | $10.00 | $1.00 | – | – | $50.00 |
| GPT-5.6 Sol (promo) | $4.00 | $0.40 | – | – | $20.00 |
| GPT-5.6 Terra | $2.00 | $0.20 | – | – | $12.00 |
| GPT-5.6 Luna | $0.20 | $0.02 | – | – | $1.20 |
| GPT-5.5 | $5.00 | $0.50 | – | – | $30.00 |
| GPT-5.5-pro, GPT-5.4-pro | $30.00 | – | – | – | $180.00 |
| GPT-5.4 | $2.50 | $0.25 | – | – | $15.00 |
| GPT-5.4-mini | $0.75 | $0.075 | – | – | $4.50 |
| GPT-5.4-nano | $0.20 | $0.02 | – | – | $1.25 |
| GPT-5.2 | $1.75 | $0.175 | – | – | $14.00 |
| GPT-5.2-pro | $21.00 | – | – | – | $168.00 |
| GPT-5.1, GPT-5 | $1.25 | $0.125 | – | – | $10.00 |
| GPT-5-mini | $0.25 | $0.025 | – | – | $2.00 |
| GPT-5-nano | $0.05 | $0.005 | – | – | $0.40 |
| GPT-5-pro | $15.00 | – | – | – | $120.00 |
| Claude Fable 5.1, Mythos 5.1 | $10.00 | $0.25 | $12.50 | $20.00 | $50.00 |
| Claude Fable 5, Mythos 5 | $10.00 | $1.00 | $12.50 | $20.00 | $50.00 |
| Claude Opus 5, 4.8, 4.7, 4.6, 4.5 | $5.00 | $0.50 | $6.25 | $10.00 | $25.00 |
| Claude Opus 4.1, Opus 4 | $15.00 | $1.50 | $18.75 | $30.00 | $75.00 |
| Claude Sonnet 5 | $2.00 | $0.20 | $2.50 | $4.00 | $10.00 |
| Claude Sonnet 4.6, 4.5, 4 | $3.00 | $0.30 | $3.75 | $6.00 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $0.10 | $1.25 | $2.00 | $5.00 |
| Claude Haiku 3.5 | $0.80 | $0.08 | $1.00 | $1.60 | $4.00 |

Pricing follows the [supplied table](researches/api-pricing-claude-openai.md);
routing follows the [research strategy](researches/model-routing-strategy-for-software-development.md).
These defaults have offline coverage, not a measured live quality or speed advantage.

Four things to know about the numbers:

- Sol uses the current $4/$0.40/$20 promotional rate, available at least through
  21 November 2026 per [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
  Recheck then; the research gives regular list pricing of $5/$0.50/$30.
- Estimates use base/short-context standard rates. OpenAI long-context
  surcharges and service-tier adjustments are not applied; large requests can
  be underestimated. Codex does not report separate cache-write counts here.
  Claude current-generation long-context variants use the base rate.
- Claude Mythos shares Claude Fable prices.
- The estimate covers the call that answered. The Claude command line also
  makes a small side call of its own, so its own reported cost runs a fraction
  of a cent higher. In the verification run the estimate was $0.0236 against the
  command line's $0.0259 for the same call.

A model with no published price shows `n/a` rather than a guess, and a run
containing one is marked partial.

### Android journeys with steps

Some questions are about what the app remembers, not about one page. A download paused twice on a weak connection. A second account on the same phone. A notification opened an hour later. A link a friend sent, opened before signing in.

Choose an Android target and the mission form grows a **Scenario** section. Open **Start from a shipped journey** and pick one of the five, or describe the journey in a sentence and press **Draft the steps** to have the AI worker write a first version. Either way you get ordered rows you can edit, reorder and remove. **Advanced: edit as YAML** shows the same steps as text for anyone who prefers it.

A row is one of five things:

- **Goal** — one instruction the AI worker carries out, such as opening a film and starting it.
- **Check** — a fact that has to become true within a number of seconds.
- **Hold** — a fact that has to stay true across a number of seconds, sampled throughout.
- **Event** — something done to the device: change the network, slow it down, wait, press home, kill the app, open a link, open a notification.
- **Manual** — hand the phone to the person sitting at it. Use it for signing in, paying and one-time codes.

A shipped journey arrives with `<placeholders>` where your own film title or account belongs. The mission refuses to save while one is left, which is what stops a template running against the wrong content.

If you do not know what the app is supposed to do, say so: set a check's policy to **Nobody has confirmed this yet**. It is then recorded as a question about intended behaviour rather than a defect, and it never lowers a score or blocks a release.

A manual step stops the recording first and waits for you. The run page shows the instruction, says the recording is paused, and offers **Continue run**. The wait counts against the mission's own time limit, and the page shows whichever is shorter. Manual steps need an emulator you can see, so start the console with `PEX_ANDROID_WINDOW=1`. When a manual step carries `ask` (for example `ask: SMS code`), you type the value on the run page instead and the console enters it into the focused field on the device, so a sign-in that sends a code to your phone can be finished without touching the emulator.

**When the AI needs data from you.** During any web run or Android journey, the AI worker no longer gives up at a phone number, email, username, password, one-time code, authenticator code or card details. It pauses the run and the page asks you for that one value. Type it and press **Continue run**, press **Skip** to let the run carry on without it, or **Stop run** to end the run. Nobody answering within five minutes, or within whatever is left of the mission's time limit, ends the run as blocked. On Android the recording stops while you answer, and you may type on the emulator yourself and continue with the box empty. On the web the field is masked in every screenshot and the value is scrubbed out of the saved evidence, but the journey video may still show it being typed. Nothing you type is stored in the run, so a replay asks again.

**When the AI needs you to choose.** Some screens offer several ways to continue: a password, a code by SMS, a code by a phone call, a Google account. Only you know which of those this test should take, so the run pauses and the page shows each option as a button. Press one and the run clicks it on the web or taps it on the device and carries on; press **Skip** to let the worker look for another way, or **Stop run** to end the run. Nothing is typed for a choice, so on Android the recording keeps running and screens are still captured. The run records which option you picked, because the name of a button is not a secret.

**Start state** decides what the device holds when the steps begin. Fresh clears the app's data, which is not a reinstall and changes nothing on the server. Keep leaves whatever the last run left. Load restores a device state you saved under **Settings → Android device**: that brings back this Mac's emulator, not an account or a paid subscription, so the steps still check those.

While the run works, each step appears with its number, its outcome in words and the evidence it used. Steps that could not be measured are listed apart from the findings, because missing evidence is a gap in coverage and not a defect.

### 4. Run and watch

Press **Run**.

Follow the timeline and open screenshots to see what happened. You can stop a run at any time.

A finished run keeps a recording of the browser. It plays at double speed so a long journey can be skimmed; the selector beside it offers 0.5x, 1x, 2x, 4x and 10x when a moment needs slowing down. Browsers may mute the sound above 2x.

Start with the normal connection. Try slower connections afterward to understand their effect.

### 5. Review the findings

A finished run opens with an **executive summary**: a headline, a short paragraph, the most serious findings and suggested next steps. The run says whether an AI worker wrote that paragraph or whether it was assembled from the record.

Under it, each area is rated from 0 to 100. A score is arithmetic, not a measurement. An area starts at 100 and loses points for the problems still open in it: 40 for a serious one, 15 for a moderate one, 5 for a minor one, and half of that where an AI suggestion has not been confirmed. Open a score to see exactly which findings reduced it. Marking a finding dismissed or resolved raises it again. An area the run could not check reads **not scored** with the reason, which is not the same as scoring zero.

A run page lists each issue once, with the pages it appeared on, so a site-wide defect reads as one row rather than one row per page. Every section and every finding carries a small copy icon, so any part can be pasted straight into a ticket or a chat. Where one of the shipped Claude Code skills helps, the run page shows its exact command with a **Copy** button.

For each finding:

1. Read what was observed.
2. Check its screenshot and recording.
3. Decide whether it needs work.
4. Assign an owner or update its status.

The **Findings** page collects every finding of the workspace in one place. It is ordered by priority, most serious first, and can be reordered by when each one was last detected. Findings are grouped by area, and each one shows the date it was last seen. Each area folds away with a click on its heading and stays folded until you open it again. Tick **Done** to close it, use **Recheck** to run its mission again, and filter by assigned or not assigned to see what still needs an owner. An assigned finding carries its owner's name at the start of the line, and a closed one is shown in grey so the open work stands out. One issue has one review state: closing a finding, or assigning it, updates every report that recorded it, so the same problem never reads open in one report and solved in another.

In Claude Code, `/pex-run-diagnose` reads a blocked or failed run for you, names the cause from the run's own evidence and offers the smallest fix.

A run reads **blocked** only when the safety policy, a missing account, a website failure or a page outside the allowed domains stopped it before it could answer. A mission whose honest answer is "this website has no prices" or "this needs an account" finishes as completed, with that answer in the summary.

A completed run means the test finished. It does **not** mean the website has no problems.

### 6. Repeat and share

Use **Replay** to check whether a finding appears again. When a replay under the same conditions no longer detects an earlier finding, that finding is marked resolved in every report that recorded it. This is not proof of a fix; a later run that sees it again records it as a new open finding.

Use **Continue this run** when a run stopped because it ran out of AI calls or steps. It appears under the status message on the run page. The browser reopens the last page in the same session, so every step, screenshot and finding already recorded is kept, and the run carries on under the same id. Add the AI calls and steps you want, up to the 60 calls and 40 steps a mission allows in total. If only the AI review was missing, continuing runs the review without repeating the journey. The recording and the browser trace continue in a new part, because parts cannot be joined into one file. Continue works for workspaces on this Mac; a run shared on a team server can only be replayed, and a benchmark visits several sites in order, so it is replayed instead.

When a run ends at its AI-call or step budget, it still spends one more AI call on the review, so the summary, the scores and the findings are complete rather than waiting for a continuation. A continued run shows each visit as a part: the timeline marks where the browser reopened, and the recording and browser trace of every part stay on the run page and in the report.

Optional automatic replay repeats a run once when it finds a potentially significant issue. It uses a separate test budget.

Use **Compare releases** after a change. Matching test conditions make comparisons more useful.

Android release comparison allows a changed APK build when the target, package, goal, applied network and measured device conditions match. It labels new, persisting and not-seen findings without editing either report. **Continue this run** remains web-only; replay uses the Android run's exact pinned APK.

Download the readable Markdown report to share with your team. In Claude Code, `/pex-findings-triage` turns the findings into one ticket each and can compare a run with a baseline, and `/pex-run-brief` writes a one-page summary for people who did not watch the run. The [skills guide](SKILLS.md) lists them all.

**Working with a team.** Sign in under **Settings** with the workspace credentials. New targets, missions and runs may be **Team** or **Only on this Mac**. A local item stays private and authoritative on that console until you explicitly share it; share its target first, then mission, then finished run. APK bytes never upload to the hub, so each execution Mac must upload the exact SHA locally. Shared raw video and logs are visible to every workspace member. Tests and AI still run on the initiating Mac.

## What are the gaps?

- **AI can be wrong or miss problems.** Review its evidence.
- **One clean run proves little.** A missing finding does not prove a fix.
- **Scores compare a run with itself.** They count the problems this run found and nothing else, so they are not a benchmark, an industry rating, or a measure of how good the website is.
- **Older AI findings may not match reliably.** Uncertain comparisons are labelled.
- **Login and protected playback need your test account and access.** Use a saved session (test persona), or put the account's identifier and password on the mission. Logins that require a one-time code are not supported.
- **Connection profiles imitate poor conditions.** Testing a real ISP requires a suitable connection endpoint.
- **The assistant types and clicks, but barely uses the keyboard.** It may press Enter in a search box and the navigation keys; any other key is refused and stops the test.
- **Payments and account changes are blocked.** Some otherwise harmless website features may also be affected.
- **Mobile screen sizes are simulated.** This is not testing on physical phones or TVs.
- **Android is a disposable-emulator lab check.** Baseline networking is supported; offline was not verified without an operator probe, and jank/rendering statistics were unavailable on the measured API 34 arm64 fixture. Missing means not measured.
- **The app is for local, internal use.** It runs one test at a time; schedules work while the service is running. A schedule runs only on the computer that created it, and only while that app is open.
- **Everyone with the website's password sees the same results.** The password says which website you may open, not who you are, so results and comments cannot be traced back to a person. A test can be cancelled from another computer only while it is still queued; once it starts, cancel it where it is running.
- **Recordings may contain private information.** Keep account sessions and evidence private. Anything captured during a test, including pages seen after signing in, is visible to everyone who has that website's password, so use test accounts.

**Best starting point:** run one small mission, inspect the evidence, and replay the most useful finding.
