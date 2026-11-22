# ParkPulse prototype — verification and audit

## Earlier V6.1 conversion baseline (historical, before latest navigation changes)

- **HTTP / shared-server API:** 63/63 passed. Includes cloud routes, separate role credentials, Guard space updates and their effects across Student/Guard/Admin, congestion and notices, settings, authorization, guard deactivation, and optimistic-concurrency checks.
- **Browser interface:** 14/14 passed. Includes slow typing without disappearing fields, all three sign-in views, live UI updates, reverse updates, visible map states, and the earlier board's 18-screen / 26-arrow verification.
- **Board navigation:** extra browser check confirmed Run opens Student, Guard and Admin routes in separately mounted frames and Back closes the live overlay.
- **Static analysis:** Python syntax and embedded JavaScript syntax passed; the HTML/CSS before the application script is byte-for-byte identical to the V6.1 source.

## Environment note

During the earlier conversion, the browser sandbox blocked direct navigation to localhost, so the browser interface test used a controlled Python HTTP bridge for API traffic, while the real server processed those requests. Thus tests cover real DOM interactions plus real HTTP backend responses, **but they do not verify deployment on Replit itself**. Perform the five-step QA walkthrough in the README after importing.

## Latest navigation and live synchronization audit — November 22, 2026

**GitHub Actions run:** https://github.com/TomTaruc/MapuaParkPulse/actions/runs/44991740493  
**Outcome:** Success. Python source syntax, embedded JavaScript syntax in the three HTML app/board files, two server-backed HTTP regression tests, and the Playwright browser smoke test all passed.

- **Navigation:** Student, Guard and Administrator headers link back to **Home** only. The central homepage contains the link to the **Flow Board**.
- **Visual Flow Board:** 20 linked visual nodes and 31 directed arrows; every endpoint resolves to a documented node. The flow begins at the actual current homepage preview, then branches to Student, Guard and Admin sign-ins. The 18 original embedded screenshot captures remain available, while the Admin sign-in node uses the same staff-sign-in artwork because the live staff form is shared.
- **Shared occupancy, confirmed in actual browser views:** Initially 20 occupied/14 available out of 34 active spaces. A Guard marking S-12 occupied changes totals to 21 occupied/13 available across Student, Guard and Admin. An Admin verifying S-12 as available returns all three to 20 occupied/14 available. Each role's live numbers and statuses changed without a manual page reload.
- **Duplicate/concurrent/permission checks:** Duplicate Guard reports do not increment counts; an outdated Admin write returns a conflict; Student cannot change server occupancy data.
- **Admin correction time:** The form now supports second-precision observations; the original minute-only time could incorrectly block a legitimate correction immediately following a Guard update.
- **Visual evidence:** This workflow uploaded `homepage-audit.png` and `flowboard-audit.png` in the `parkpulse-browser-audit` artifact.
- **Mechanism and limits:** The three role pages poll the same authenticated server state about every 650 ms when online. It is near-real-time polling (not push notifications). Backgrounded tabs or network failure can delay updates. The browser and HTTP tests exercised a running local copy of the app—not a deployed Replit instance.

The original /legacy-board artwork is preserved as a historical screen-capture reference and is not claimed to contain the new homepage layout.
