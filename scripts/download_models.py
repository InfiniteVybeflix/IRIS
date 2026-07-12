#!/usr/bin/env python3
"""
IRIS Model Downloader — Smart, resumable, background-aware downloads.
Features:
- Automatic hardware detection → optimal model selection
- Resume interrupted downloads
- Retry with exponential backoff
- Background download support (daemon mode)
- Progress bars with speed display
- SHA256 verification
- Parallel downloads
"""

import os
import sys
import time
import hashlib
import json
import threading
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from datetime import datetime

# Import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hardware_detector import HardwareDetector, HardwareProfile
from model_registry import MODEL_REGISTRY, get_model_for_hardware, ModelVariant, ModelConfig


@dataclass
class DownloadJob:
    """A single download task."""
    model_id: str
    variant_key: str
    url: str
    destination: str
    expected_size: int
    sha256: str
    status: str = "pending"  # pending, downloading, paused, completed, failed
    progress_bytes: int = 0
    retries: int = 0
    error_message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ModelDownloader:
    """Intelligent model downloader with resume and retry."""

    def __init__(self, models_dir: str = "models", max_retries: int = 5, 
                 chunk_size: int = 8192, parallel: int = 2):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.chunk_size = chunk_size
        self.parallel = parallel
        self.jobs: List[DownloadJob] = []
        self.state_file = self.models_dir / ".download_state.json"
        self.lock = threading.Lock()
        self._running = False
        self._threads: List[threading.Thread] = []

        # Load previous state
        self._load_state()

    def _load_state(self):
        """Load download state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                for job_data in data.get('jobs', []):
                    job = DownloadJob(**job_data)
                    # Convert string timestamps back to datetime
                    if job.started_at and isinstance(job.started_at, str):
                        job.started_at = datetime.fromisoformat(job.started_at)
                    if job.completed_at and isinstance(job.completed_at, str):
                        job.completed_at = datetime.fromisoformat(job.completed_at)
                    self.jobs.append(job)
            except Exception as e:
                print(f"Warning: Could not load state: {e}")

    def _save_state(self):
        """Save download state to disk."""
        with self.lock:
            data = {'jobs': []}
            for job in self.jobs:
                job_dict = {
                    'model_id': job.model_id,
                    'variant_key': job.variant_key,
                    'url': job.url,
                    'destination': job.destination,
                    'expected_size': job.expected_size,
                    'sha256': job.sha256,
                    'status': job.status,
                    'progress_bytes': job.progress_bytes,
                    'retries': job.retries,
                    'error_message': job.error_message,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                }
                data['jobs'].append(job_dict)

            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)

    def add_job(self, model_id: str, variant_key: Optional[str] = None,
                hardware_profile: Optional[HardwareProfile] = None) -> bool:
        """Add a model download job. Auto-selects variant if not specified."""
        if model_id not in MODEL_REGISTRY:
            print(f"Error: Model '{model_id}' not found in registry")
            return False

        config = MODEL_REGISTRY[model_id]

        # Auto-select variant if not specified
        if variant_key is None:
            if hardware_profile is None:
                detector = HardwareDetector()
                hardware_profile = detector.detect()

            variant = get_model_for_hardware(
                model_id, 
                hardware_profile.tier,
                hardware_profile.gpu_vram_gb,
                hardware_profile.total_ram_gb
            )
            if variant is None:
                print(f"Error: No suitable variant found for {model_id} on this hardware")
                return False
            # Find the key for this variant
            for k, v in config.variants.items():
                if v.name == variant.name:
                    variant_key = k
                    break
        else:
            if variant_key not in config.variants:
                print(f"Error: Variant '{variant_key}' not found for {model_id}")
                return False
            variant = config.variants[variant_key]

        # Determine destination
        type_dir = config.type.value
        dest = self.models_dir / type_dir / variant.filename
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Check if already downloaded
        if dest.exists():
            file_size = dest.stat().st_size
            if file_size == variant.size_gb * 1024**3:
                print(f"Model {model_id}/{variant_key} already downloaded ({dest})")
                return True

        job = DownloadJob(
            model_id=model_id,
            variant_key=variant_key,
            url=variant.download_url,
            destination=str(dest),
            expected_size=int(variant.size_gb * 1024**3),
            sha256=variant.sha256,
        )

        with self.lock:
            # Check if job already exists
            for existing in self.jobs:
                if existing.model_id == model_id and existing.variant_key == variant_key:
                    if existing.status == "completed":
                        print(f"Model {model_id}/{variant_key} already completed")
                        return True
                    print(f"Job {model_id}/{variant_key} already queued (status: {existing.status})")
                    return True
            self.jobs.append(job)

        self._save_state()
        print(f"Added download job: {model_id}/{variant_key} -> {dest}")
        return True

    def _download_with_resume(self, job: DownloadJob, progress_callback: Optional[Callable] = None):
        """Download a file with resume support."""
        import urllib.request
        import urllib.error

        dest_path = Path(job.destination)
        temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

        # Check existing progress
        start_byte = 0
        if temp_path.exists():
            start_byte = temp_path.stat().st_size
            job.progress_bytes = start_byte

        # Build request with resume header
        headers = {}
        if start_byte > 0:
            headers['Range'] = f'bytes={start_byte}-'

        req = urllib.request.Request(job.url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                if start_byte > 0 and response.status == 206:
                    total_size += start_byte
                elif start_byte > 0 and total_size == 0:
                    # Server doesn't support resume, restart
                    start_byte = 0
                    temp_path.unlink(missing_ok=True)

                job.expected_size = total_size or job.expected_size

                mode = 'ab' if start_byte > 0 else 'wb'
                with open(temp_path, mode) as f:
                    downloaded = start_byte
                    last_time = time.time()
                    last_bytes = downloaded

                    while True:
                        chunk = response.read(self.chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        job.progress_bytes = downloaded

                        # Calculate speed
                        now = time.time()
                        if now - last_time >= 1.0:
                            speed = (downloaded - last_bytes) / (now - last_time)
                            last_time = now
                            last_bytes = downloaded

                            if progress_callback:
                                progress_callback(job, downloaded, total_size, speed)

                        # Save state periodically
                        if downloaded % (1024 * 1024 * 10) == 0:  # Every 10MB
                            self._save_state()

            # Verify download
            if job.sha256:
                actual_hash = self._calculate_sha256(temp_path)
                if actual_hash != job.sha256:
                    raise ValueError(f"SHA256 mismatch: expected {job.sha256}, got {actual_hash}")

            # Move temp to final
            temp_path.rename(dest_path)
            job.status = "completed"
            job.completed_at = datetime.now()
            print(f"\n✓ Completed: {job.model_id}/{job.variant_key}")

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.retries += 1
            print(f"\n✗ Failed: {job.model_id}/{job.variant_key} — {e}")
            if job.retries < self.max_retries:
                delay = min(2 ** job.retries, 300)  # Max 5 min backoff
                print(f"  Retrying in {delay}s... (attempt {job.retries + 1}/{self.max_retries})")
                time.sleep(delay)
                job.status = "pending"

    def _calculate_sha256(self, path: Path) -> str:
        """Calculate SHA256 of a file."""
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _progress_bar(self, job: DownloadJob, downloaded: int, total: int, speed: float):
        """Display progress bar."""
        if total > 0:
            percent = downloaded / total * 100
            bar_len = 30
            filled = int(bar_len * downloaded / total)
            bar = '█' * filled + '░' * (bar_len - filled)
            speed_mb = speed / (1024 * 1024)
            sys.stdout.write(f"\r{job.model_id}: [{bar}] {percent:.1f}% {speed_mb:.1f} MB/s")
            sys.stdout.flush()

    def _worker(self):
        """Worker thread for downloading."""
        while self._running:
            job = None
            with self.lock:
                for j in self.jobs:
                    if j.status == "pending":
                        j.status = "downloading"
                        j.started_at = datetime.now()
                        job = j
                        break

            if job is None:
                time.sleep(1)
                continue

            self._save_state()
            self._download_with_resume(job, self._progress_bar)
            self._save_state()

    def start(self, background: bool = False):
        """Start downloading."""
        self._running = True

        if background:
            print(f"Starting {self.parallel} background download workers...")
            for i in range(self.parallel):
                t = threading.Thread(target=self._worker, daemon=True, name=f"Downloader-{i}")
                t.start()
                self._threads.append(t)
            print("Downloads running in background. Use --status to check progress.")
        else:
            print(f"Starting downloads (foreground mode)...")
            self._worker()

    def stop(self):
        """Stop all downloads."""
        self._running = False
        for t in self._threads:
            t.join(timeout=5)
        self._save_state()

    def status(self):
        """Print current download status."""
        print("\n" + "=" * 70)
        print("Download Status")
        print("=" * 70)

        pending = sum(1 for j in self.jobs if j.status == "pending")
        downloading = sum(1 for j in self.jobs if j.status == "downloading")
        completed = sum(1 for j in self.jobs if j.status == "completed")
        failed = sum(1 for j in self.jobs if j.status == "failed")

        print(f"Pending: {pending} | Downloading: {downloading} | Completed: {completed} | Failed: {failed}")
        print("-" * 70)

        for job in self.jobs:
            if job.status == "downloading" and job.expected_size > 0:
                percent = job.progress_bytes / job.expected_size * 100
                print(f"  [{job.status.upper():12}] {job.model_id}/{job.variant_key} — {percent:.1f}%")
            else:
                print(f"  [{job.status.upper():12}] {job.model_id}/{job.variant_key}")

        print("=" * 70)

    def install_dependencies(self, model_id: str):
        """Install pip dependencies for a model."""
        if model_id not in MODEL_REGISTRY:
            print(f"Model {model_id} not found")
            return

        config = MODEL_REGISTRY[model_id]
        if config.pip_dependencies:
            print(f"Installing dependencies for {model_id}...")
            import subprocess
            cmd = [sys.executable, "-m", "pip", "install"] + config.pip_dependencies
            subprocess.run(cmd, check=False)


def main():
    parser = argparse.ArgumentParser(description="IRIS Model Downloader")
    parser.add_argument("--detect", action="store_true", help="Detect hardware and show recommendations")
    parser.add_argument("--download", nargs='+', help="Download specific models (e.g., qwen3 musicgen)")
    parser.add_argument("--download-all", action="store_true", help="Download all models that fit hardware")
    parser.add_argument("--variant", help="Specify variant (e.g., q4_8b, medium)")
    parser.add_argument("--background", "-b", action="store_true", help="Run downloads in background")
    parser.add_argument("--status", "-s", action="store_true", help="Show download status")
    parser.add_argument("--install-deps", nargs='+', help="Install dependencies for models")
    parser.add_argument("--models-dir", default="models", help="Directory to store models")
    parser.add_argument("--list", action="store_true", help="List all available models")

    args = parser.parse_args()

    if args.detect:
        detector = HardwareDetector()
        profile = detector.detect()
        print(json.dumps({
            "cpu": profile.cpu_model,
            "ram_gb": round(profile.total_ram_gb, 1),
            "gpu": profile.gpu_name,
            "vram_gb": round(profile.gpu_vram_gb, 1),
            "tier": profile.tier,
            "recommended_quantization": profile.recommended_quantization,
            "max_model_size_gb": round(profile.max_model_size_gb, 1),
        }, indent=2))
        return

    if args.list:
        print("Available Models:")
        for mid, config in MODEL_REGISTRY.items():
            print(f"  {mid:15} — {config.name} ({config.type.value})")
        return

    if args.status:
        downloader = ModelDownloader(models_dir=args.models_dir)
        downloader.status()
        return

    if args.install_deps:
        downloader = ModelDownloader(models_dir=args.models_dir)
        for model_id in args.install_deps:
            downloader.install_dependencies(model_id)
        return

    if args.download or args.download_all:
        detector = HardwareDetector()
        profile = detector.detect()

        downloader = ModelDownloader(models_dir=args.models_dir)

        if args.download_all:
            for model_id in MODEL_REGISTRY.keys():
                downloader.add_job(model_id, hardware_profile=profile)
        else:
            for model_id in args.download:
                downloader.add_job(model_id, variant_key=args.variant, hardware_profile=profile)

        downloader.start(background=args.background)

        if not args.background:
            downloader.stop()
            downloader.status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
