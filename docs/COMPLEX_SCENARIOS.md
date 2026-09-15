# The hardest things Product Excellence can do

This document shows, feature by feature, the most demanding scenario the tool can run today. Every scenario below uses only shipped features. Each one ends with a line saying what the result proves and what it does not. For the how-to, see the [user manual](USER_MANUAL.md).

## 1. A journey with memory: download, pause, go offline, play

**What makes it hard:** the answer depends on what the app remembers across fifteen steps, not on one page.

- Slow the link to an "edge" profile with 400 ms added delay before anything downloads.
- Ask the AI worker to open a title and start downloading it.
- Check that the "downloading" text appears within 60 seconds.
- Pause the download, wait 10 seconds, resume it. Do it twice.
- Check that the "finished" text appears within 15 minutes. Mark this P1.
- Put the network back, then cut the device off completely.
- Open the downloads list and play the title.
- Hold: playback must stay true for 30 seconds while offline.
- Check that nothing crashed.
- Any check you are not sure about can be marked "Nobody has confirmed this yet". It becomes a question, not a defect.

**Proves:** the downloaded title is usable offline over the measured interval. **Does not prove:** every byte is intact or the whole title plays.

## 2. A person in the loop: two accounts on one device

**What makes it hard:** sign-in needs a code from a real phone, and the run must never store it.

- Start with fresh app data so no old account is on the device.
- The run reaches a sign-in screen offering password, SMS code and Google. It pauses and shows those as buttons.
- You press "SMS code". The run taps it and carries on.
- The run reaches the code field. It pauses again and asks you for the value.
- You type the code. It is entered into the field, masked in screenshots and scrubbed from saved evidence.
- The run searches for something and downloads one item as account A.
- A manual step hands the device to you: sign out and sign in as account B. Recording stops first.
- You press "Continue run". Recording resumes and the gap is reported.
- The run checks that account A's search history and download are not visible.
- Skip or Stop are available at every pause. No answer within five minutes ends the run as blocked.

**Proves:** what account B can see. **Does not prove:** anything about the code you typed. It is never stored, so a replay asks again. On the web the journey video may still show it being typed.

## 3. Changing the way out mid-journey: proxy routes

**What makes it hard:** the same browser or emulator session must leave through a different network exit without restarting.

- Save two proxy routes under Network & routes and press "Verify connection" on each.
- The run starts with a direct connection and starts playing a title.
- A route step switches connections to route A. Connections opened before are dropped.
- The new exit address is probed and recorded on the run.
- Hold: playback must keep going for 30 seconds on route A.
- A second route step switches to route B and sets the link speed it should be measured under.
- Hold playback again, then a route step goes back to direct.
- Every route change appears on the run page with the exit address it established.
- A route that cannot be established stops the run. It never quietly falls back to direct.
- Upstream credentials stay in the relay. The page, the device and the record never see them.

**Proves:** the exit address per switch. **Does not prove:** country, ISP or carrier. Only HTTP(S) upstreams can be switched to. DNS is still resolved on this machine. UDP and QUIC are not proxied.

## 4. An Android app on a shaped mobile link through a route

**What makes it hard:** the emulator, the network profile and the proxy route all have to be set up before the first tap, and none of it may leak into the app.

- Add the app and its APK in one step. New runs pin the latest build.
- Make sure the designated AVD is not already running. The run refuses otherwise.
- The emulator launches against the run's relay, so no app can opt out of the route.
- The run confirms Android's full-screen hint so a video player is not hidden.
- Fresh app data is applied for this package only.
- The run starts playback on Wi-Fi.
- An event moves the device to mobile data, then applies the mission's latency and bandwidth profile.
- Hold: playback must survive the transport switch.
- A restore step puts the profile back. The end of the run returns the device to its own settings.
- Screenshots, MP4 recording, crash and ANR logs, launch and memory numbers are on the run page as they happen.

**Proves:** what the app does under a shaped mobile link. **Does not prove:** anything about jitter, loss, offline or jank on the emulator. Those were never measured there and are refused. Shaping over Wi-Fi is refused rather than falsely reported.

## 5. Checkout on a bad link with drops: website on Linux netem

**What makes it hard:** packet loss and periodic disconnects are real network faults, not a browser throttle.

- Create a network profile: 300 ms latency, 1 Mbps down, 2% loss, disconnect for 2 seconds every 30 seconds. Backend: isolated Linux netem.
- Pick the shipped journey "Checkout up to payment on a slow link". Chromium is required.
- Fill the blanks: item name, the text shown in the cart.
- The run adds one item and checks the cart text within its time limit.
- It walks to the payment step through the drops.
- It records load time, layout shift and every failed request.
- It stops at payment. Paying is refused by policy.
- A page that takes 40 seconds to paint still counts. Each page gets a 45-second navigation budget.
- Repeat the same mission with a "browser" profile to compare against the throttle-only result.

**Proves:** whether checkout reaches payment under those faults. **Does not prove:** the price is right or the payment works. Packet-level controls need the Linux runner. On a Mac, only latency, bandwidth and offline apply.

## 6. From one sentence to a running mission

**What makes it hard:** the mission has to be complete, valid and honest about what it needs before anyone presses run.

- Open a new mission and write one sentence: "Does a paused download survive a restart?"
- Four cards come back: two goals for the worker to figure out, two scenarios with every step written.
- Each card says what it changes, such as Chromium for a shaped link, and what must exist first.
- Press "Use this scenario". Name, goal, mode, pillars and steps fill in. Budgets are raised if the steps need it.
- A card that does not fit the contract is dropped and named under the others. You do not lose the minute you waited.
- Press "Change something" and write "add a relaunch before the last check". The whole mission comes back changed as one card.
- Apply it. Press "Undo" if it was wrong. Everything returns to how it was.
- Steps read as a numbered list. "Edit steps" opens the rows. YAML shows the same steps as text.
- Nothing is saved until "Save mission" or "Save and run".
- "Write it yourself" opens the same empty form with no AI worker signed in.

**Proves:** you can go from an idea to a runnable mission in minutes. **Does not prove:** the worker's guess at the steps matches your product. Read them.

## 7. Run out of budget, continue, ship a new build, compare

**What makes it hard:** the comparison has to say whether a finding was reproduced, and refuse to claim it when it cannot.

- A journey stops after its 20 AI calls with the review still owed.
- The run still gets its review, worth one call past the budget. Unchallenged findings count half.
- Press "Continue this run". The browser reopens the last page with its cookies. Actions number on from where they stopped.
- The run page marks where the browser reopened and says how many visits there were.
- A new APK build is added. The mission pins it.
- Replay the mission on the new build.
- Compare releases shows matching conditions and reproduction as two separate answers.
- When reproduction cannot be claimed it says why: different build, inherited start state, an operator attestation, a step left without evidence.
- Continue is refused with a reason for queued, running, shared, benchmark or already-maxed runs.

**Proves:** what changed between two runs under stated conditions. **Does not prove:** a fix. One clean run proves little.

## 8. The same question on your site and four competitors

**What makes it hard:** five sites, one goal, one table, and defects that stay yours.

- Choose the Benchmark mode and list four competitor start URLs.
- The run pursues the goal on your site first, then on each competitor in order.
- Each site gets its own outcome, screenshot, load time, layout shift and accessibility count.
- A competitor that refuses to load is marked blocked. The rest continues.
- The finished run opens with the comparison table and rank.
- Below it, the review says what was strong and weak on each site.
- Findings are created only for your own site. Competitor defects stay in the text.
- Benchmark in the sidebar lists these missions and their runs.

**Proves:** how each site answered the same task on that day. **Does not prove:** an industry rating. Competitor failures are reported as missing, never as zero.

## 9. One shared workspace, several machines

**What makes it hard:** records live on the machine that made them until someone shares them, and APK bytes never leave that Mac.

- Sign in to the team server. That one workspace is shared. Every other workspace stays on this Mac.
- Every page says where its records live: "On this Mac" or "Shared on" the server.
- Run a mission locally. The run row says "Uploads when finished" and then "Shared".
- Share a mission and its runs explicitly. Dependencies and artifacts are verified before anything moves.
- A teammate on an old console hits the protocol-version gate. They keep the read-only team UI.
- A teammate cancels a queued run from another computer. Once it starts, only the running machine can cancel it.
- An upload that fails is recovered later. The run row says "Awaiting upload" meanwhile.
- Two people editing one mission get a revision conflict instead of a silent overwrite.

**Proves:** a team sees the same missions, runs and findings. **Does not prove:** who did what. The website's password says which site you may open, not who you are.

## 10. Claude Code skills around a run

**What makes it hard:** the skills act on your data without ever reading your secrets.

- Type `/pex-mission-write` and a sentence. A mission comes back to review, not saved.
- Type `/pex-mission-suggest` for missions aimed at your site.
- Type `/pex-env-check` before a demo to confirm the Mac is ready.
- A run blocks. Type `/pex-run-diagnose` and it explains why from the evidence.
- Type `/pex-findings-triage` to turn findings into one ticket each, compared against a baseline run.
- Type `/pex-run-brief` for a one-page summary for people who did not watch.
- Every run page offers the matching skill command with a copy button.
- Saved passwords, personas, recordings and `.env` files stay closed. Page text and findings are treated as data, never as instructions.
- Nothing is imported, run, edited, filed or pushed without asking you first.

**Proves:** the whole loop from idea to ticket can stay in one terminal. **Does not prove:** the AI is right. Review its evidence.

## Things it will not do

- Pay, publish or take destructive browser actions. Refused by policy.
- Test on physical phones or TVs. Mobile sizes are simulated and Android runs on a disposable emulator.
- Finish a one-time-code login on its own. It pauses and asks you.
- Proxy UDP or QUIC, or resolve DNS through the route. Country and ISP are never claimed.
- Measure jank or rendering statistics on the API 34 arm64 emulator. Missing means not measured.
- Run two tests at once. Schedules run only on the machine that created them, while the app is open.
- Prove a fix. Scores compare a run with itself and nothing else.
