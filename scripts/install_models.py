#!/usr/bin/env python3
"""
IRIS Model Installer — One script to detect, download, and wire everything.
Usage:
    python install_models.py --all          # Download all models that fit your hardware
    python install_models.py --text       # Download only text models
    python install_models.py --image      # Download only image models
    python install_models.py --audio      # Download only audio models
    python install_models.py --video      # Download only video models
    python install_models.py --3d         # Download only 3D models
    python install_models.py --motion     # Download only motion models
    python install_models.py --robotics   # Download only robotics models
    python install_models.py --science    # Download only science models
    python install_models.py --model qwen3 musicgen  # Download specific models
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add script directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hardware_detector import HardwareDetector
from model_registry import MODEL_REGISTRY, ModelType
from download_models import ModelDownloader
from generate_wrappers import generate_all_wrappers


def check_prerequisites():
    """Check if Python, pip, and git are available."""
    print("Checking prerequisites...")

    checks = {
        "python": ["python", "--version"],
        "pip": ["pip", "--version"],
        "git": ["git", "--version"],
    }

    all_good = True
    for name, cmd in checks.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"  ✓ {name}: {result.stdout.strip()}")
            else:
                print(f"  ✗ {name}: not found")
                all_good = False
        except Exception:
            print(f"  ✗ {name}: not found")
            all_good = False

    return all_good


def install_base_dependencies():
    """Install base dependencies needed by all models."""
    print("\nInstalling base dependencies...")
    base_deps = [
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "diffusers",
        "accelerate",
        "huggingface-hub",
        "safetensors",
        "numpy",
        "pillow",
        "requests",
        "tqdm",
        "psutil",
    ]

    cmd = [sys.executable, "-m", "pip", "install"] + base_deps
    subprocess.run(cmd, check=False)
    print("Base dependencies installed.")


def main():
    parser = argparse.ArgumentParser(
        description="IRIS Model Installer — Detect hardware, download models, generate wrappers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                Download all models that fit your hardware
  %(prog)s --text               Download only text/LLM models
  %(prog)s --image --audio      Download image and audio models
  %(prog)s --model qwen3 flux2  Download specific models by ID
  %(prog)s --detect-only        Just detect hardware, don't download
  %(prog)s --wrappers-only      Only generate wrapper files
        """
    )

    parser.add_argument("--all", action="store_true", help="Download all compatible models")
    parser.add_argument("--text", action="store_true", help="Download text models")
    parser.add_argument("--image", action="store_true", help="Download image models")
    parser.add_argument("--audio", action="store_true", help="Download audio models")
    parser.add_argument("--video", action="store_true", help="Download video models")
    parser.add_argument("--3d", dest="three_d", action="store_true", help="Download 3D models")
    parser.add_argument("--motion", action="store_true", help="Download motion models")
    parser.add_argument("--robotics", action="store_true", help="Download robotics models")
    parser.add_argument("--science", action="store_true", help="Download science models")
    parser.add_argument("--model", nargs='+', help="Download specific model IDs")
    parser.add_argument("--detect-only", action="store_true", help="Only detect hardware")
    parser.add_argument("--wrappers-only", action="store_true", help="Only generate wrappers")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--background", "-b", action="store_true", help="Download in background")
    parser.add_argument("--models-dir", default="models", help="Directory to store models")

    args = parser.parse_args()

    # Detect hardware
    print("=" * 70)
    print("IRIS v9 — Model Installer")
    print("=" * 70)

    detector = HardwareDetector()
    profile = detector.detect()

    print(f"\nHardware Profile:")
    print(f"  CPU: {profile.cpu_model} ({profile.cpu_count} cores)")
    print(f"  RAM: {profile.total_ram_gb:.1f} GB")
    print(f"  GPU: {profile.gpu_name}")
    if profile.gpu_available:
        print(f"  VRAM: {profile.gpu_vram_gb:.1f} GB")
        print(f"  CUDA: {profile.cuda_version or 'N/A'}")
    print(f"  Tier: {profile.tier.upper()}")
    print(f"  Recommended quantization: {profile.recommended_quantization}")
    print(f"  Max model size: {profile.max_model_size_gb:.1f} GB")
    print(f"  Storage available: {profile.available_storage_gb:.1f} GB")

    if args.detect_only:
        detector.save(profile)
        print(f"\nProfile saved to hardware_profile.json")
        return

    # Check prerequisites
    if not check_prerequisites():
        print("\n✗ Prerequisites check failed. Please install missing tools.")
        return

    # Install base dependencies
    if not args.skip_deps:
        install_base_dependencies()

    # Determine which models to download
    models_to_download = []

    if args.all:
        models_to_download = list(MODEL_REGISTRY.keys())
    elif args.text:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.TEXT]
    elif args.image:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.IMAGE]
    elif args.audio:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.AUDIO]
    elif args.video:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.VIDEO]
    elif args.three_d:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.THREE_D]
    elif args.motion:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.MOTION]
    elif args.robotics:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.ROBOTICS]
    elif args.science:
        models_to_download = [k for k, v in MODEL_REGISTRY.items() if v.type == ModelType.SCIENCE]
    elif args.model:
        models_to_download = args.model
    else:
        # Default: download all that fit
        print("\nNo specific models requested. Downloading all compatible models...")
        models_to_download = list(MODEL_REGISTRY.keys())

    # Filter by hardware compatibility
    compatible = []
    incompatible = []

    for model_id in models_to_download:
        if model_id not in MODEL_REGISTRY:
            print(f"  ⚠ Unknown model: {model_id}")
            continue

        config = MODEL_REGISTRY[model_id]
        # Check if any variant fits
        fits = False
        for variant in config.variants.values():
            if profile.gpu_available:
                if variant.min_vram_gb <= profile.gpu_vram_gb * 0.9:
                    fits = True
                    break
            else:
                if variant.min_ram_gb <= profile.total_ram_gb * 0.7:
                    fits = True
                    break

        if fits:
            compatible.append(model_id)
        else:
            incompatible.append(model_id)

    print(f"\nCompatible models: {len(compatible)}")
    for m in compatible:
        print(f"  ✓ {m}")

    if incompatible:
        print(f"\nIncompatible models (skipped): {len(incompatible)}")
        for m in incompatible:
            print(f"  ✗ {m}")

    if not compatible:
        print("\nNo compatible models found for your hardware.")
        return

    # Download models
    if not args.wrappers_only:
        print(f"\nStarting downloads...")
        downloader = ModelDownloader(models_dir=args.models_dir)

        for model_id in compatible:
            downloader.add_job(model_id, hardware_profile=profile)

        downloader.start(background=args.background)

        if not args.background:
            downloader.stop()
            downloader.status()

    # Generate wrappers
    print(f"\nGenerating wrapper files...")
    generated = generate_all_wrappers(args.models_dir)
    print(f"Generated {len(generated)} wrapper files")

    # Create __init__.py files
    for subdir in ["text", "image", "audio", "video", "3d", "motion", "robotics", "science"]:
        init_path = Path(args.models_dir) / subdir / "__init__.py"
        init_path.parent.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            with open(init_path, 'w') as f:
                f.write(f'"""IRIS {subdir} models module."""\n')

    print("\n" + "=" * 70)
    print("Installation complete!")
    print("=" * 70)
    print(f"\nModels directory: {Path(args.models_dir).absolute()}")
    print(f"Wrapper files: {len(generated)}")
    print(f"\nNext steps:")
    print(f"  1. Models will download in background (if --background was used)")
    print(f"  2. Check status: python download_models.py --status")
    print(f"  3. Use models in IRIS via the generated wrapper classes")
    print(f"  4. Example: from models.text.qwen3_wrapper import Qwen3Engine")
    print("=" * 70)


if __name__ == "__main__":
    main()
