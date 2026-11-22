# Mapúa ParkPulse — Replit-ready functional prototype

This package contains the working V6.1 ParkPulse UI with its original CSS and illustrated parking map, plus an unchanged 18-screen / 26-connection presentation board. The only UI-code changes are role-specific browser token storage and single-origin routing, required to run all roles from a single Replit web server.

## Import and run

1. Open **https://replit.com/import** and select **ZIP**. Upload `Mapua_ParkPulse_Replit_Ready.zip`.
2. Open the imported app. Its Run command is configured as `python3 server.py`.
3. Click **Run**, then open **Webview/Preview**. The connection board is the first page at `/`.
4. On the board select **Run live prototype**, or open `/student`, `/guard`, and `/admin` directly from the same Replit preview URL.
5. Keep the Replit app running while demonstrating. Open a separate tab/browser to show synchronization.

### Demo credentials (not real school accounts)

| Role | Login | Password |
| --- | --- | --- |
| Student | `202600001` | `DemoStudent#26` |
| Guard | `guard.demo` | `DemoGuard#26` |
| Administrator | `admin.demo` | `DemoAdmin#26` |

### Interaction / synchronization

* Student, Guard, Admin have separate browser-session tokens within one domain.
* The local Python server is the authority for shared parking data; role screens poll it approximately every 650 ms.
* Guards can update a specific parking space, and Student / Admin dashboards reflect occupancy and availability changes on their next poll. Congestion and notices also come from the shared state.
* The state and demo guard accounts are written to local JSON files in the **Replit workspace**, and can persist across normal Run/Stop cycles in that workspace. These files are created automatically and are excluded from Git.

### Cloud hosting limitations / safety

* This is a **classroom demonstration prototype**, not an institutional production system. The space IDs and counts are provisional demo values; they are not verified live Mapúa Makati inventory.
* **Demo credentials are supplied in this package.** Anyone with access to a publicly shared hosted version could log into those demo accounts. Do not use real student data, real credentials, or an unrestricted public deployment.
* **Published Replit Deployments can use ephemeral file systems.** Do not claim that data survives redeployments, multiple instances, or server restarts of a published app. For durable public deployment, migrate JSON state and sessions to a managed database, enable real authentication, and review infrastructure costs.
* Replit's online preview may have account, usage, and session limits. This ZIP is **prepared for import**; it cannot be installed into your personal Replit account from ChatGPT.

### File guide

`server.py`: one-server Python API and data store. `.replit`: Run command and port. `index.html`: original three-role application with only route/session configuration adapted. `StageBoard.html`: full screen-connection board with same images/arrows plus role iframe links. `connections.json`: preserved connection data.

### QA checklist for your presentation

- [ ] Board shows 18 pages and arrows
- [ ] Student, Guard and Admin sign in individually
- [ ] Guard marks S-12 occupied; Student / Admin occupancy updates
- [ ] Guard marks S-12 available; all three agree
- [ ] Guard congestion changes appear in Student / Admin views
- [ ] Admin notice is visible on Student view
- [ ] Admin guard deactivation revokes Guard access
- [ ] Reload each role independently; no cross-role login
