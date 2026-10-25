# IRIS Redesign — Deployment Package (2026-10-25)

This ZIP contains every file changed or created in this session, in their correct
folder structure. Copy the folders over your repo root (or `git add` them) and push.

## Why the site was plain text
`vercel.json` rewrote `/static/(.*)` to the filesystem path `static/$1`, which does
not exist in the Vercel build output — so **every** stylesheet, script, font and
image 404'd (verified live: `/static/iris-logo.png` → 404). The fix routes all
traffic to the Flask lambda, which bundles `static/**` via `includeFiles` and
serves files with correct MIME types.

## Files in this package
| File | Status | Purpose |
|------|--------|---------|
| `vercel.json` | **fixed** | Routes `/static/*` (and everything else) to the Flask lambda |
| `templates/iris.html` | **rewritten** | Single app shell: Chat · Agents workspace · Apps hub · Settings (hash-routed) |
| `static/css/iris.css` | **rewritten** | Professional design system — Inter + Fira Code self-hosted, dark & light themes, no sci-fi |
| `static/js/iris.js` | **rewritten** | All client logic: chat, agent tabs, apps, settings, model/script runner — every failure surfaces a toast |
| `api/routes/scripts.py` | **new** | `/api/scripts` — model registry + allowlisted script runner (jobs with live output) |
| `app.py` | **fixed** | Registers scripts blueprint; `/settings` now redirects to `/#/settings`; `/favicon.ico` served; missing `import json` fixed (streaming crash) |
| `cortex/base_cortex.py` | included | The earlier `_conn` fix, in case it is not yet in your repo |

## Files to DELETE from your repo
The old separate pages are replaced by the unified shell:

```bash
git rm templates/iris_face.html templates/iris_face_3d.html templates/iris_voice.html templates/settings.html
```

## How to apply
```bash
# from your repo root
unzip -o IRIS-redesign-2026-10-25.zip -d /path/to/your-repo
cd /path/to/your-repo
git rm templates/iris_face.html templates/iris_face_3d.html templates/iris_voice.html templates/settings.html
git add app.py vercel.json templates/iris.html static/css/iris.css static/js/iris.js api/routes/scripts.py cortex/base_cortex.py
git commit -m "Redesign UI as unified multi-agent workspace; fix static asset 404s on Vercel"
git push
```
Vercel will auto-deploy. Hard-refresh the page (Ctrl/Cmd+Shift+R) after deploy.

## What you get
- **Chat** — orchestrator-backed responses, process steps, stop/retry, browser dictation, optional TTS.
- **Agents** — real OMNIS registry (30 agents, real specialties), delegate tasks; every run opens its own tab with the agent's real output; live activity from OMNIS execution log.
- **Apps** — Calendar (real CRUD + .ics export), Notes (real CRUD, pin, search), Calculator (real engine + statistics/units via /api/math), Projects (real generator), Vision (real server frames + analysis), Math (sympy), Phone (honest ADB bridge status).
- **Settings** — Provider config (ported & improved), **Models & Scripts** (the repo's scripts now run from Settings: pull models with `install_models.py`, hardware detection — real stdout/stderr, allowlisted), Integrations, System (status, autonomous queue, self-analysis).

## Honest limitations (by design, no simulation)
- On Vercel the filesystem is ephemeral: model installs won't persist and large
  downloads hit the function timeout. Settings → Models & scripts shows this
  banner and reports the real script output either way.
- Phone features need the ADB bridge running on a host with a connected device.
- No fake data anywhere: empty states say so, errors name the failing endpoint.
