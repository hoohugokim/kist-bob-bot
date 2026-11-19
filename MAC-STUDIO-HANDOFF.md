# Moving KIST-Bob-Bot to the Mac Studio

Keep the existing Dooray channel. Its roughly 100 subscribers and message history stay in place. Move the publisher and give the incoming admin control of the channel, webhook, repository and server. During rehearsal, Linux serves subscribers while the Mac posts to a private test channel. At cutover, exactly one machine may send to production.

## Dates and owners

Proposed for November 2026, all times KST. Move the cutover to the next staffed evening if a rehearsal check is still open.

| When | Owner | Exit condition |
|---|---|---|
| Thu 19–Fri 20 | Outgoing maintainer + admin | Agree on the release below. Admin can invite members, manage incoming hooks in the existing channel and obtain the source without the departing account. Name a backup operator and agree who can start the Linux fallback. |
| Mon 23–Tue 24, daytime | Admin, with maintainer available | Mac produces a menu and photo in the sandbox, runs the scheduler after logout and passes an agreed reboot test. Linux still delivers production meals. |
| Tue 24, 18:40 | Maintainer stops Linux. Admin starts Mac. | Dinner photo polling ended at 18:25. Both operators reconcile the final state, then verify one active publisher. |
| Wed 25–Thu 26 | Admin operates, maintainer observes | Check two service days of lunch and dinner, photo follow-ups when available and the matching state files. Admin demonstrates recovery and a calendar edit. |
| Fri 27, with Mon 30 as buffer | Admin + backup | Record acceptance and the new contact. Retire the Linux posting credential and fallback after sign-off. If delayed, assign a KIST owner with tested access to the fallback before the maintainer leaves. |

## Which version to deploy

At the start of the November 19 review, GitHub `main` and the local committed `HEAD` both pointed to `3b3057b12a7171c2594638353397bc04a0252482`. The running Linux unit pointed at this working directory. The table describes the differences found before preparing this guide.

| Files | Change since GitHub | Decision |
|---|---|---|
| `kbb_agent.sh` | Checks the manual closure calendar before the deadline probe and records a per-slot missed marker on a listed day. | Keep. An explicitly closed day stays quiet even if the agent starts late. |
| `kist_bob_bot.sh`, `post_slot_images.sh` | The menu command returns 4 on a listed date, including the manual `all` path. The photo command exits quietly before scraping. | Keep both entry points consistent with the scheduler. |
| `kbb_common.sh`, `skip_dates.txt` | Two untracked files supply the shared date matcher and editable calendar. The original entries were October 5 and 9, 2026. The handoff calendar adds December 25 and all 15 nationwide weekday public holidays in 2027. | Include both in the same release as their callers. Review upcoming closures with the cafeteria. |
| `README.md` | Documents the calendar, accepted date formats and `KBB_SKIP_DATES_FILE`. | Keep the operator instructions. |
| Scraper, notifier, sample config, avatar and Linux unit in Git | Identical to GitHub. The **installed** Linux unit separately sets `KBB_LIFECYCLE_NOTICE=0`. | Reuse these files and carry the quiet lifecycle setting into launchd. Keep the Linux unit for rollback. |

An offline comparison on Linux used the same sample meal for both versions. The ordinary lunch and photo payloads matched. With the cafeteria reporting a meal on a date listed as closed, the local version suppressed menus, photos and late warnings. The earlier GitHub revision generated them. The agent remembers a skip by writing a missed marker for each slot, even before lunch. If a closure is cancelled the same day, review those markers and channel history with the scheduler stopped before reopening the affected slots. Removing just the calendar entry leaves the stamped slots suppressed.

**Release to hand over.** Use the reviewed GitHub commit containing this guide, [the calendar](skip_dates.txt) and the [launchd template](deploy/macos/local.kist-bob-bot.plist). Record its full SHA in the handoff and deploy that exact revision. Give the admin and backup ongoing repository access under KIST control. If the repository moves, check the public avatar URL in the bot configuration. Update the README invitation contact once the new owner accepts.

For a visit with limited GitHub access, run `git bundle create /path/to/kbb-handoff.bundle main` from the published checkout. On the Mac, clone the bundle in place of the GitHub URL and check out the same agreed SHA. The bundle carries the committed calendar, guide and plist together.

## Before the visit

- **Outgoing maintainer** supplies the release or visit kit, the current skip calendar, expected bot name and avatar, and a known good menu/photo date. November 18 had both lunch and dinner markers. Keep Linux enabled through rehearsal.
- **Incoming admin** secures Mac administrator access, a KIST-managed standard account for the service, the KIST network connection, and a private Dooray channel with its own incoming hook. Arrange a maintenance window for the shared Mac and confirm who can unlock it after a power loss.
- **Together** verify the admin can manage the **existing production channel** using their own account. Prefer an admin-managed hook in that channel. Keep the Linux hook valid through acceptance if a second hook is available. If reusing one hook, confirm who can manage or replace it after offboarding. Use an approved secret store or private transfer for hook URLs. The bot uses incoming hooks, Bash, Python 3's standard library and curl. A personal API token or model server is unnecessary.
- Transfer source from the reviewed release and runtime state from the final snapshot below. Provision secrets separately. The private handoff notes, sandbox credentials, historical dry runs, caches and other workstation projects can stay on Linux.

## Rehearse on the Mac Studio

The template assumes a standard account named `kbb`, its home at `/Users/kbb`, and a checkout at `/Users/kbb/kist-bob-bot`. Use the actual account and absolute paths consistently if the site uses different names. A system LaunchDaemon runs the existing scheduler once the OS can access its files, including after GUI logout. Arrange desktop sleep and power-recovery settings with the server owner, and test the site's FileVault unlock procedure. [Apple launchd guide](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) · [Mac desktop power settings](https://support.apple.com/guide/mac-help/mchle41a6ccd/mac) · [FileVault startup](https://support.apple.com/guide/deployment/intro-to-filevault-dep82064ec40/web)

1. As `kbb`, clone the repository into `/Users/kbb/kist-bob-bot`, run `git checkout --detach <agreed-full-SHA>` in the clone with the actual release ID and confirm it with `git rev-parse HEAD`. In the checkout, run the following as `kbb`. The proposed `PATH` matches the template. If the Mac uses a different managed Python, set its directory in both places. Confirm Python runs without a developer-tools installation prompt.

   ```sh
   cd /Users/kbb/kist-bob-bot
   export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
   command -v python3
   python3 -c 'import ssl, urllib.request, kist_menu_scraper'
   /bin/bash --version
   curl --version
   umask 077
   ops=/Users/kbb/kbb-ops
   mkdir -p "$ops"/manual-state "$ops"/rehearsal-state "$ops"/state
   chmod 700 "$ops"
   ```

2. Create `$ops/sandbox.conf` from `dooray.conf.example` with mode 600 and enter only the private channel's hook there. Prepare a separate `$ops/production.conf` with mode 600 and the agreed production identity. Confirm both files belong to `kbb`. Keep the URLs out of shell history, Git, logs and tickets.

3. Still as `kbb`, choose a registered day with known photos. Use the isolated state even for dry runs because pre-existing markers can short-circuit the commands. These subshells keep test settings out of subsequent operations.

   ```sh
   meal_day=20261118
   (
     export KBB_LOCAL_CONF="$ops/sandbox.conf" KBB_STATE_DIR="$ops/manual-state" KBB_DRY_RUN=1
     ./kist_bob_bot.sh lunch --date "$meal_day" && ./post_slot_images.sh lunch --date "$meal_day"
   )
   ```

   Inspect the two payloads in `.dryrun/`. Then send the same pair to the **private channel**, after confirming the sandbox hook's destination in Dooray.

   ```sh
   (
     export KBB_LOCAL_CONF="$ops/sandbox.conf" KBB_STATE_DIR="$ops/manual-state" KBB_DRY_RUN=0
     ./kist_bob_bot.sh lunch --date "$meal_day" && ./post_slot_images.sh lunch --date "$meal_day"
   )
   ```

   Check the date, Korean menu text, visible bot identity and rendered photo. Repeat the sandbox pair and verify the channel still has exactly one of each. A silent photo command alone proves little because it can also mean missing pictures or a failed scrape. For a listed date such as `20261009`, repeat the dry-run menu command with that date and expect exit 4. If the upstream no longer serves the historical meal, use a newly observed service day.

4. As the **Mac admin**, install the rehearsal template. It selects `sandbox.conf` and `rehearsal-state`.

   ```sh
   plist=/Library/LaunchDaemons/local.kist-bob-bot.plist
   job=system/local.kist-bob-bot
   sudo install -o root -g wheel -m 0644 /Users/kbb/kist-bob-bot/deploy/macos/local.kist-bob-bot.plist "$plist"
   sudo plutil -lint "$plist"
   sudo launchctl enable "$job"
   sudo launchctl bootstrap system "$plist"
   sudo launchctl print "$job"
   ```

   Confirm a running PID, the sandbox config/state paths, and a startup entry in `/Users/kbb/kbb-ops/agent.log`. Check `agent.err` for failures. Observe a scheduled sandbox meal from this job. Log out and verify it keeps running. During the agreed window, reboot and verify the job and KIST network access after the site's unlock procedure. If the host needs a GUI VPN session, cannot wake reliably, or cannot send the sandbox card, keep Linux serving while the admin resolves it.

## Cut over after the dinner photo window

1. **Mac admin** closes rehearsal. In the same admin shell (or reset `plist` and `job` as above), run `sudo launchctl disable "$job"` then `sudo launchctl bootout "$job"`. Confirm `sudo launchctl print "$job"` reports the service is absent. Disabling it also prevents a reboot from loading it during the transfer.
2. **Linux maintainer**, from the production checkout as the service owner, runs the following after the final dinner cycle. Check any cron entries or manually started copies too. Proceed when the unit is inactive and disabled and there is no KBB sender still running.

   ```sh
   systemctl --user disable --now kist-bob-bot.service
   systemctl --user is-active kist-bob-bot.service
   systemctl --user is-enabled kist-bob-bot.service
   ```

3. **Together**, compare today's channel posts with `.state/`. For each date and slot, `YYYYMMDD-lunch-menu` records the menu, `YYYYMMDD-lunch` the photo and `YYYYMMDD-lunch-menu-missed` a closed, skipped or missed slot. Dinner follows the same convention. A missing photo stamp is legitimate if no photo was available. Resolve discrepancies against the channel before starting either host. A successful send can precede its stamp, and separate hosts cannot see one another's stamps.
4. **Linux maintainer** snapshots the complete production state after the stop. Substitute the effective state directory if the unit has an override. Transfer just this archive and its checksum over an approved private channel or encrypted visit media. Keep the stopped Linux checkout and config available for rollback.

   ```sh
   snap=$(mktemp -d)
   tar -C .state -czf "$snap/kbb-state.tgz" .
   (cd "$snap" && sha256sum kbb-state.tgz > kbb-state.sha256)
   ```

5. **Mac admin**, from the folder containing the two transferred files, checks the digest and loads the archive into the empty production state directory owned by `kbb`. Pause if that directory already contains markers and reconcile them first. Do not use either rehearsal state directory. An evening start with missing same-day stamps can immediately send late warnings.

   ```sh
   shasum -a 256 -c kbb-state.sha256
   sudo -u kbb ls -A /Users/kbb/kbb-ops/state
   sudo -u kbb tar -xzf - -C /Users/kbb/kbb-ops/state < kbb-state.tgz
   sudo -u kbb ls -l /Users/kbb/kbb-ops/state
   ```

6. **Mac admin** points the stopped job at the verified state and production hook. Run each step after the preceding check passes. Confirm the two paths in the plist, the readability of the config as `kbb`, and Linux's disabled status before enabling the job.

   ```sh
   sudo /usr/libexec/PlistBuddy -c 'Set :EnvironmentVariables:KBB_LOCAL_CONF /Users/kbb/kbb-ops/production.conf' "$plist"
   sudo /usr/libexec/PlistBuddy -c 'Set :EnvironmentVariables:KBB_STATE_DIR /Users/kbb/kbb-ops/state' "$plist"
   sudo plutil -lint "$plist"
   sudo plutil -p "$plist"
   sudo -u kbb test -r /Users/kbb/kbb-ops/production.conf
   sudo -u kbb test -w /Users/kbb/kbb-ops/state
   sudo launchctl enable "$job"
   sudo launchctl bootstrap system "$plist"
   sudo launchctl print "$job"
   ```

   Confirm `state = running`, a PID, and the production paths. The job suppresses online/offline cards just like the installed Linux unit. Observe the first **scheduled** post as the production test. A manual `all` post bypasses the slot guard.

## Verify, recover and sign off

**Next two service days.** The admin and an ordinary channel member check one menu per registered slot (11:00 lunch, 17:00 dinner), one photo follow-up when images appear (11:05–11:55 and 17:05–18:25), and corresponding files in `/Users/kbb/kbb-ops/state`. Menus retry about every 30 seconds until 11:55/17:55. A yellow notice can follow a missed deadline. Check the calendar, cafeteria data and `agent.err` before treating silence as a host failure. A full missed window does not backfill a meal. Record the first successful Mac lunch and dinner in the private handoff log.

**Roll back** if the Mac cannot stay running, reach the hook, or deliver a registered meal in time. Start recovery while the current meal window is open if feasible.

1. On the Mac, run `sudo launchctl disable system/local.kist-bob-bot` and `sudo launchctl bootout system/local.kist-bob-bot` for the loaded job. Verify it is absent. If the host is unreachable, isolate its network or revoke its distinct posting hook before enabling Linux. With a shared hook, secure a working Linux-only credential or positively isolate the Mac first.
2. With both publishers stopped, archive the Mac's **production** state using the snapshot procedure above (`tar -C /Users/kbb/kbb-ops/state`; use `shasum -a 256` on macOS). Verify the digest on Linux and extract into its production `.state/` as the service owner, retaining existing markers. If the Mac state is unavailable or a delivery was interrupted, inspect today's Dooray history and the skip calendar. Restore the appropriate same-day markers for confirmed menus, photos, warnings or closures before restarting. Leave pending slots eligible.
3. Verify the original Linux config uses a still-valid production hook. Run `systemctl --user enable --now kist-bob-bot.service` and verify with `systemctl --user is-active kist-bob-bot.service` and `journalctl --user -u kist-bob-bot.service -n 30`. Observe the next eligible post. Schedule another cutover only after the Mac passes rehearsal again.

**Acceptance.** The admin records the deployed commit SHA, channel owner and backup, credential location, private support contact, install/state/log paths, and who handles reboot recovery. Have the admin demonstrate status and logs, a skip-date edit against the sandbox, and how to stop a sender before recovery. Agree on log rotation and a private backup of production config and recent state. After the observation period, update the invitation contact, revoke the retired hook or rotate a shared hook to the admin's custody, verify the next scheduled post with that credential, and remove the old host's secret copies through the site's offboarding procedure.
