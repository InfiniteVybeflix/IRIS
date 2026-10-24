"""IRIS Scripts & Models API — run the repo's own maintenance scripts from Settings.

The scripts (scripts/*.py) help users pull and run models and inspect the
machine. They are controlled from Settings → "Models & Scripts": the UI lists
the model registry (scripts/model_registry.py) and can start an allowlisted
installer as a background job, streaming its real output back.

Endpoints:
  GET  /api/scripts            — model catalog + allowlisted scripts + environment info
  POST /api/scripts/run        — start an allowlisted script as a background job
  GET  /api/scripts/jobs       — list known jobs
  GET  /api/scripts/jobs/<id>  — one job's status + captured output

Security:
  - Only allowlisted scripts can run. The client never passes free-form shell
    arguments; arguments are built server-side from validated values
    (model ids are checked against MODEL_REGISTRY, categories against ModelType).
  - Output is captured (never executed), tails are capped to keep responses small.
  - On Vercel's serverless filesystem nothing persists after the function ends —
    this is surfaced honestly to the UI via environment info.
"""
import os
import sys
import time
import uuid
import shutil
import threading
import subprocess
import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
scripts_bp = Blueprint("iris_scripts", __name__)

# Repo root = three levels up from this file (api/routes/scripts.py).
ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"

# Hard execution limits: Vercel functions are killed around 60s, so running
# longer locally-only jobs there would just time out — fail fast and honestly.
TIMEOUT_VERCEL = 55
TIMEOUT_LOCAL = 1800

_OUTPUT_TAIL = 24_000  # max bytes of stdout/stderr kept per job

_jobs = {}
_jobs_lock = threading.Lock()


def _vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def _registry():
    """Load scripts/model_registry.py (stdlib-only module — safe on serverless)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "iris_model_registry", str(ROOT / "scripts" / "model_registry.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _catalog():
    reg = _registry()
    models = []
    for mid, m in reg.MODEL_REGISTRY.items():
        models.append({
            "id": mid,
            "name": m.name,
            "type": m.type.value,
            "description": m.description,
            "pip_dependencies": list(m.pip_dependencies or []),
            "variants": [
                {
                    "key": k,
                    "name": v.name,
                    "quant": v.quant,
                    "size_gb": v.size_gb,
                    "min_vram_gb": v.min_vram_gb,
                    "min_ram_gb": v.min_ram_gb,
                    "filename": v.filename,
                }
                for k, v in m.variants.items()
            ],
        })
    return models


def _allowed_specs():
    """Allowlisted scripts and the validated arguments each accepts."""
    cats = sorted({m["type"] for m in _catalog()})
    return {
        "install_models": {
            "label": "Install models",
            "cmd": [sys.executable, str(ROOT / "scripts" / "install_models.py")],
            "description": "Detect hardware, download models and generate wrappers.",
            "accepts": {
                "all": "flag", "model": "model_id", "category": cats,
            },
        },
        "hardware_detector": {
            "label": "Detect hardware",
            "cmd": [sys.executable, str(ROOT / "scripts" / "hardware_detector.py")],
            "description": "Report CPU/GPU/RAM so IRIS can pick fitting model variants.",
            "accepts": {},
        },
        "generate_wrappers": {
            "label": "Generate model wrappers",
            "cmd": [sys.executable, str(ROOT / "scripts" / "generate_wrappers.py")],
            "description": "Generate Python wrapper modules for installed models.",
            "accepts": {},
        },
    }


def _build_args(script_id: str, body: dict, spec: dict) -> list:
    """Translate a validated request body into CLI args. Never trusts raw input."""
    accepts = spec["accepts"]
    args = []
    if script_id in ("install_models", "download_models"):
        if body.get("all"):
            args.append("--all")
        model = body.get("model")
        if model:
            if model not in {m["id"] for m in _catalog()}:
                raise ValueError(f"Unknown model id: {model}")
            args += ["--model", model]
        category = body.get("category")
        if category:
            if category not in accepts.get("category", []):
                raise ValueError(f"Unknown category: {category}")
            args.append(f"--{category}")
    return args


def _run_job(job_id: str, cmd: list, timeout: int):
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), timeout=timeout,
            capture_output=True, text=True, errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1", "TERM": "dumb"},
        )
        out, err, code, killed = proc.stdout or "", proc.stderr or "", proc.returncode, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        code, killed = 124, True
        err += f"\n[job killed after {timeout}s timeout]"
    except Exception as e:
        out, err, code, killed = "", f"{type(e).__name__}: {e}", 1, False

    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job.update({
                "status": "timeout" if killed else ("done" if code == 0 else "failed"),
                "exit_code": code,
                "stdout": out[-_OUTPUT_TAIL:],
                "stderr": err[-_OUTPUT_TAIL:],
                "duration_s": round(time.time() - started, 1),
                "finished_at": time.time(),
            })


@scripts_bp.route("/api/scripts", methods=["GET"])
def scripts_index():
    """Model catalog + allowlisted scripts + honest environment info."""
    serverless = _vercel()
    try:
        models = _catalog()
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to load model registry: {e}"}), 500

    installed_gb = 0.0
    if MODELS_DIR.exists():
        for p in MODELS_DIR.rglob("*"):
            try:
                if p.is_file():
                    installed_gb += p.stat().st_size / 1e9
            except OSError:
                pass

    env = {
        "serverless": serverless,
        "python": sys.version.split()[0],
        "platform": f"{os.uname().sysname} {os.uname().machine}" if hasattr(os, "uname") else os.name,
        "models_dir": str(MODELS_DIR),
        "models_dir_exists": MODELS_DIR.exists(),
        "installed_gb": round(installed_gb, 2),
        "free_disk_gb": round(shutil.disk_usage(str(ROOT)).free / 1e9, 1),
        "note": (
            "Running on Vercel: the filesystem is ephemeral and functions are time-limited, "
            "so downloads will not persist and large models will hit the timeout. "
            "For persistent installs run IRIS on a machine you control (Docker / local)."
            if serverless else
            "Running on a persistent host: downloads land in ./models and survive restarts."
        ),
    }
    return jsonify({
        "success": True,
        "models": models,
        "scripts": [
            {"id": sid, "label": s["label"], "description": s["description"],
             "accepts": s["accepts"], "command": " ".join(s["cmd"][1:])}
            for sid, s in _allowed_specs().items()
        ],
        "environment": env,
    })


@scripts_bp.route("/api/scripts/run", methods=["POST"])
def scripts_run():
    """Start an allowlisted script as a background job.

    Body: {"script": "install_models", "model": "qwen3"? , "category": "text"?,
           "all": bool?}
    Returns: {"success": true, "job_id": "..."} — poll /api/scripts/jobs/<id>.
    """
    body = request.get_json() or {}
    script_id = body.get("script", "")
    specs = _allowed_specs()
    if script_id not in specs:
        return jsonify({"success": False,
                        "error": f"Script '{script_id}' is not allowlisted. Allowed: {', '.join(specs)}"}), 400
    spec = specs[script_id]

    try:
        args = _build_args(script_id, body, spec)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    cmd = spec["cmd"] + args
    job_id = uuid.uuid4().hex[:12]
    timeout = TIMEOUT_VERCEL if _vercel() else TIMEOUT_LOCAL
    with _jobs_lock:
        # Keep the registry bounded — drop finished jobs older than 1h.
        now = time.time()
        for jid in [j for j, v in _jobs.items()
                    if v.get("finished_at") and now - v["finished_at"] > 3600]:
            _jobs.pop(jid, None)
        _jobs[job_id] = {
            "job_id": job_id, "script": script_id, "command": " ".join(cmd[1:]),
            "status": "running", "started_at": now, "timeout_s": timeout,
            "stdout": "", "stderr": "", "exit_code": None, "duration_s": None,
        }

    t = threading.Thread(target=_run_job, args=(job_id, cmd, timeout), daemon=True)
    t.start()
    logger.info("[scripts] job %s started: %s", job_id, " ".join(cmd))
    return jsonify({"success": True, "job_id": job_id, "command": " ".join(cmd[1:]),
                    "timeout_s": timeout,
                    "poll": f"/api/scripts/jobs/{job_id}"})


@scripts_bp.route("/api/scripts/jobs", methods=["GET"])
def scripts_jobs():
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)
        return jsonify({"success": True, "jobs": jobs})


@scripts_bp.route("/api/scripts/jobs/<job_id>", methods=["GET"])
def scripts_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return jsonify({"success": False, "error": "Unknown job id"}), 404
        return jsonify({"success": True, "job": dict(job)})
