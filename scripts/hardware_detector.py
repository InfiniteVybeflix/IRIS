#!/usr/bin/env python3
"""
IRIS Hardware Detector — Analyzes system capabilities for optimal model selection.
"""
import os
import sys
import subprocess
import json
import platform
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

@dataclass
class HardwareProfile:
    """Complete hardware profile for model selection."""
    # CPU
    cpu_count: int
    cpu_model: str
    cpu_arch: str

    # RAM
    total_ram_gb: float
    available_ram_gb: float

    # GPU
    gpu_available: bool
    gpu_count: int
    gpu_name: str
    gpu_vram_gb: float
    gpu_compute_capability: str
    cuda_available: bool
    cuda_version: str
    rocm_available: bool
    mps_available: bool  # Apple Silicon

    # Storage
    total_storage_gb: float
    available_storage_gb: float

    # Network
    internet_available: bool
    download_speed_mbps: Optional[float]

    # IRIS Classification
    tier: str  # "edge", "consumer", "pro", "datacenter"
    recommended_quantization: str  # "q4", "q5", "q8", "fp16", "fp32"
    max_model_size_gb: float


class HardwareDetector:
    """Detects all hardware capabilities."""

    def detect(self) -> HardwareProfile:
        profile = HardwareProfile(
            cpu_count=self._get_cpu_count(),
            cpu_model=self._get_cpu_model(),
            cpu_arch=platform.machine(),
            total_ram_gb=self._get_total_ram(),
            available_ram_gb=self._get_available_ram(),
            gpu_available=False,
            gpu_count=0,
            gpu_name="None",
            gpu_vram_gb=0.0,
            gpu_compute_capability="",
            cuda_available=False,
            cuda_version="",
            rocm_available=False,
            mps_available=False,
            total_storage_gb=self._get_total_storage(),
            available_storage_gb=self._get_available_storage(),
            internet_available=self._check_internet(),
            download_speed_mbps=None,
            tier="edge",
            recommended_quantization="q4",
            max_model_size_gb=4.0,
        )

        # Detect GPU
        self._detect_gpu(profile)

        # Classify tier
        self._classify_tier(profile)

        return profile

    def _get_cpu_count(self) -> int:
        return os.cpu_count() or 1

    def _get_cpu_model(self) -> str:
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            elif platform.system() == "Darwin":
                result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], 
                                      capture_output=True, text=True)
                return result.stdout.strip()
            elif platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                return winreg.QueryValueEx(key, "ProcessorNameString")[0]
        except Exception:
            pass
        return platform.processor() or "Unknown"

    def _get_total_ram(self) -> float:
        try:
            import psutil
            return psutil.virtual_memory().total / (1024**3)
        except ImportError:
            if platform.system() == "Linux":
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal:" in line:
                            return int(line.split()[1]) / (1024**2)
        return 8.0  # Default assumption

    def _get_available_ram(self) -> float:
        try:
            import psutil
            return psutil.virtual_memory().available / (1024**3)
        except ImportError:
            return self._get_total_ram() * 0.5

    def _get_total_storage(self) -> float:
        try:
            import shutil
            total, _, _ = shutil.disk_usage("/")
            return total / (1024**3)
        except Exception:
            return 100.0

    def _get_available_storage(self) -> float:
        try:
            import shutil
            _, used, free = shutil.disk_usage("/")
            return free / (1024**3)
        except Exception:
            return 50.0

    def _check_internet(self) -> bool:
        try:
            import urllib.request
            urllib.request.urlopen("https://huggingface.co", timeout=5)
            return True
        except Exception:
            return False

    def _detect_gpu(self, profile: HardwareProfile):
        """Detect NVIDIA, AMD, Apple Silicon GPUs."""
        # Try PyTorch first
        try:
            import torch
            profile.cuda_available = torch.cuda.is_available()
            profile.mps_available = torch.backends.mps.is_available() if hasattr(torch.backends, "mps") else False

            if profile.cuda_available:
                profile.gpu_available = True
                profile.gpu_count = torch.cuda.device_count()
                profile.gpu_name = torch.cuda.get_device_name(0)
                profile.gpu_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                cc = torch.cuda.get_device_capability(0)
                profile.gpu_compute_capability = f"{cc[0]}.{cc[1]}"
                profile.cuda_version = torch.version.cuda or ""
        except ImportError:
            pass

        # Try NVIDIA-smi
        if not profile.gpu_available:
            try:
                result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    parts = result.stdout.strip().split(",")
                    if len(parts) >= 2:
                        profile.gpu_available = True
                        profile.gpu_name = parts[0].strip()
                        vram_str = parts[1].strip().replace(" MiB", "").replace(" MB", "")
                        profile.gpu_vram_gb = int(vram_str) / 1024
                        profile.gpu_count = 1
                        profile.cuda_available = True
            except Exception:
                pass

        # Try ROCm (AMD)
        if not profile.gpu_available:
            try:
                result = subprocess.run(["rocminfo"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and "GPU" in result.stdout:
                    profile.gpu_available = True
                    profile.rocm_available = True
                    profile.gpu_name = "AMD GPU"
                    profile.gpu_count = 1
            except Exception:
                pass

    def _classify_tier(self, profile: HardwareProfile):
        """Classify system into performance tiers."""
        if profile.gpu_available and profile.gpu_vram_gb >= 24:
            profile.tier = "datacenter"
            profile.recommended_quantization = "fp16"
            profile.max_model_size_gb = min(profile.gpu_vram_gb * 0.8, 80)
        elif profile.gpu_available and profile.gpu_vram_gb >= 12:
            profile.tier = "pro"
            profile.recommended_quantization = "q8"
            profile.max_model_size_gb = min(profile.gpu_vram_gb * 0.8, 30)
        elif profile.gpu_available and profile.gpu_vram_gb >= 6:
            profile.tier = "consumer"
            profile.recommended_quantization = "q5"
            profile.max_model_size_gb = min(profile.gpu_vram_gb * 0.8, 15)
        elif profile.total_ram_gb >= 16:
            profile.tier = "consumer"
            profile.recommended_quantization = "q4"
            profile.max_model_size_gb = min(profile.total_ram_gb * 0.3, 8)
        else:
            profile.tier = "edge"
            profile.recommended_quantization = "q4"
            profile.max_model_size_gb = min(profile.total_ram_gb * 0.25, 4)

    def save(self, profile: HardwareProfile, path: str = "hardware_profile.json"):
        with open(path, 'w') as f:
            json.dump(asdict(profile), f, indent=2)

    def load(self, path: str = "hardware_profile.json") -> HardwareProfile:
        with open(path, 'r') as f:
            data = json.load(f)
        return HardwareProfile(**data)


if __name__ == "__main__":
    detector = HardwareDetector()
    profile = detector.detect()
    print(json.dumps(asdict(profile), indent=2))
    detector.save(profile)
    print(f"\nHardware profile saved to hardware_profile.json")
    print(f"Tier: {profile.tier.upper()} | Max model: {profile.max_model_size_gb:.1f}GB | Quant: {profile.recommended_quantization}")
