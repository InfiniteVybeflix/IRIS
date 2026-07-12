#!/usr/bin/env python3
"""
IRIS Model Registry — Complete catalog of all AI models with hardware-aware variants.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class ModelType(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    THREE_D = "3d"
    MOTION = "motion"
    ROBOTICS = "robotics"
    SCIENCE = "science"

class Quantization(Enum):
    Q4 = "q4"      # 4-bit, smallest, fastest
    Q5 = "q5"      # 5-bit, balanced
    Q8 = "q8"      # 8-bit, high quality
    FP16 = "fp16"  # Half precision
    FP32 = "fp32"  # Full precision

@dataclass
class ModelVariant:
    """A specific variant of a model (different size/quantization)."""
    name: str
    quant: str
    size_gb: float
    min_vram_gb: float
    min_ram_gb: float
    download_url: str
    filename: str
    sha256: str = ""  # For verification

@dataclass
class ModelConfig:
    """Complete configuration for a model family."""
    id: str
    name: str
    type: ModelType
    description: str

    # Variants by quantization
    variants: Dict[str, ModelVariant] = field(default_factory=dict)

    # Default wrapper template
    wrapper_template: str = ""

    # Dependencies
    pip_dependencies: List[str] = field(default_factory=list)
    system_dependencies: List[str] = field(default_factory=list)

    # IRIS integration
    iris_module_path: str = ""  # Where to place the wrapper in IRIS
    iris_class_name: str = ""   # Class name for IRIS integration


# ============================================================
# MODEL DEFINITIONS
# ============================================================

MODEL_REGISTRY = {
    # ─── TEXT & CODING (LLMs) ───
    "qwen3": ModelConfig(
        id="qwen3",
        name="Qwen3",
        type=ModelType.TEXT,
        description="Alibaba's Qwen3 — best open-source multilingual LLM with tool use",
        variants={
            "q4_8b": ModelVariant(
                name="Qwen3-8B-Q4",
                quant="q4",
                size_gb=5.2,
                min_vram_gb=6,
                min_ram_gb=8,
                download_url="https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/qwen3-8b-q4_k_m.gguf",
                filename="qwen3-8b-q4_k_m.gguf",
            ),
            "q5_8b": ModelVariant(
                name="Qwen3-8B-Q5",
                quant="q5",
                size_gb=6.4,
                min_vram_gb=8,
                min_ram_gb=10,
                download_url="https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/qwen3-8b-q5_k_m.gguf",
                filename="qwen3-8b-q5_k_m.gguf",
            ),
            "q4_27b": ModelVariant(
                name="Qwen3-27B-Q4",
                quant="q4",
                size_gb=16.8,
                min_vram_gb=20,
                min_ram_gb=24,
                download_url="https://huggingface.co/Qwen/Qwen3-27B-GGUF/resolve/main/qwen3-27b-q4_k_m.gguf",
                filename="qwen3-27b-q4_k_m.gguf",
            ),
        },
        pip_dependencies=["llama-cpp-python", "transformers", "torch"],
        iris_module_path="models/text/",
        iris_class_name="Qwen3Engine",
    ),

    "gemma4": ModelConfig(
        id="gemma4",
        name="Gemma 4",
        type=ModelType.TEXT,
        description="Google's Gemma 4 — efficient instruction-tuned LLM",
        variants={
            "q4_9b": ModelVariant(
                name="Gemma-4-9B-Q4",
                quant="q4",
                size_gb=5.8,
                min_vram_gb=6,
                min_ram_gb=8,
                download_url="https://huggingface.co/bartowski/google_gemma-4-9b-it-GGUF/resolve/main/google_gemma-4-9b-it-Q4_K_M.gguf",
                filename="gemma-4-9b-it-Q4_K_M.gguf",
            ),
            "q4_27b": ModelVariant(
                name="Gemma-4-27B-Q4",
                quant="q4",
                size_gb=17.2,
                min_vram_gb=20,
                min_ram_gb=24,
                download_url="https://huggingface.co/bartowski/google_gemma-4-27b-it-GGUF/resolve/main/google_gemma-4-27b-it-Q4_K_M.gguf",
                filename="gemma-4-27b-it-Q4_K_M.gguf",
            ),
        },
        pip_dependencies=["llama-cpp-python", "transformers"],
        iris_module_path="models/text/",
        iris_class_name="Gemma4Engine",
    ),

    # ─── IMAGE GENERATION ───
    "flux2": ModelConfig(
        id="flux2",
        name="FLUX.2",
        type=ModelType.IMAGE,
        description="Black Forest Labs FLUX.2 — state-of-the-art text-to-image",
        variants={
            "dev_fp16": ModelVariant(
                name="FLUX.2-Dev-FP16",
                quant="fp16",
                size_gb=23.8,
                min_vram_gb=24,
                min_ram_gb=32,
                download_url="https://huggingface.co/black-forest-labs/FLUX.2-dev/resolve/main/flux2-dev.safetensors",
                filename="flux2-dev.safetensors",
            ),
            "schnell_fp16": ModelVariant(
                name="FLUX.2-Schnell-FP16",
                quant="fp16",
                size_gb=23.8,
                min_vram_gb=12,
                min_ram_gb=16,
                download_url="https://huggingface.co/black-forest-labs/FLUX.2-schnell/resolve/main/flux2-schnell.safetensors",
                filename="flux2-schnell.safetensors",
            ),
        },
        pip_dependencies=["diffusers", "torch", "transformers", "accelerate"],
        iris_module_path="models/image/",
        iris_class_name="Flux2Engine",
    ),

    "sdxl": ModelConfig(
        id="sdxl",
        name="Stable Diffusion XL",
        type=ModelType.IMAGE,
        description="SDXL — robust open image generation",
        variants={
            "base_fp16": ModelVariant(
                name="SDXL-Base-FP16",
                quant="fp16",
                size_gb=6.9,
                min_vram_gb=8,
                min_ram_gb=12,
                download_url="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
                filename="sd_xl_base_1.0.safetensors",
            ),
        },
        pip_dependencies=["diffusers", "torch", "transformers", "accelerate"],
        iris_module_path="models/image/",
        iris_class_name="SDXLEngine",
    ),

    # ─── AUDIO & MUSIC ───
    "musicgen": ModelConfig(
        id="musicgen",
        name="MusicGen",
        type=ModelType.AUDIO,
        description="Meta's MusicGen — text-to-music generation",
        variants={
            "small": ModelVariant(
                name="MusicGen-Small",
                quant="fp32",
                size_gb=1.5,
                min_vram_gb=4,
                min_ram_gb=8,
                download_url="https://huggingface.co/facebook/musicgen-small/resolve/main/pytorch_model.bin",
                filename="musicgen-small.bin",
            ),
            "medium": ModelVariant(
                name="MusicGen-Medium",
                quant="fp32",
                size_gb=3.7,
                min_vram_gb=8,
                min_ram_gb=12,
                download_url="https://huggingface.co/facebook/musicgen-medium/resolve/main/pytorch_model.bin",
                filename="musicgen-medium.bin",
            ),
            "large": ModelVariant(
                name="MusicGen-Large",
                quant="fp32",
                size_gb=7.8,
                min_vram_gb=16,
                min_ram_gb=24,
                download_url="https://huggingface.co/facebook/musicgen-large/resolve/main/pytorch_model.bin",
                filename="musicgen-large.bin",
            ),
        },
        pip_dependencies=["audiocraft", "torch", "transformers"],
        iris_module_path="models/audio/",
        iris_class_name="MusicGenEngine",
    ),

    "xtts_v2": ModelConfig(
        id="xtts_v2",
        name="XTTS v2",
        type=ModelType.AUDIO,
        description="Coqui XTTS v2 — voice cloning and text-to-speech",
        variants={
            "default": ModelVariant(
                name="XTTS-v2",
                quant="fp16",
                size_gb=1.9,
                min_vram_gb=4,
                min_ram_gb=6,
                download_url="https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth",
                filename="xtts-v2.pth",
            ),
        },
        pip_dependencies=["TTS", "torch", "torchaudio"],
        iris_module_path="models/audio/",
        iris_class_name="XTTSv2Engine",
    ),

    "bark": ModelConfig(
        id="bark",
        name="Bark",
        type=ModelType.AUDIO,
        description="Suno Bark — expressive text-to-speech",
        variants={
            "small": ModelVariant(
                name="Bark-Small",
                quant="fp32",
                size_gb=3.9,
                min_vram_gb=6,
                min_ram_gb=8,
                download_url="https://huggingface.co/suno/bark/resolve/main/pytorch_model.bin",
                filename="bark.bin",
            ),
        },
        pip_dependencies=["transformers", "torch", "scipy"],
        iris_module_path="models/audio/",
        iris_class_name="BarkEngine",
    ),

    # ─── VIDEO GENERATION ───
    "wan27": ModelConfig(
        id="wan27",
        name="Wan 2.7",
        type=ModelType.VIDEO,
        description="Wan 2.7 — text/image-to-video generation",
        variants={
            "t2v_14b_fp16": ModelVariant(
                name="Wan-2.7-T2V-14B-FP16",
                quant="fp16",
                size_gb=28.0,
                min_vram_gb=32,
                min_ram_gb=48,
                download_url="https://huggingface.co/Wan-AI/Wan2.1-T2V-14B/resolve/main/diffusion_pytorch_model.fp16.safetensors",
                filename="wan2.7-t2v-14b-fp16.safetensors",
            ),
            "t2v_1_3b_fp16": ModelVariant(
                name="Wan-2.7-T2V-1.3B-FP16",
                quant="fp16",
                size_gb=2.6,
                min_vram_gb=6,
                min_ram_gb=12,
                download_url="https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/diffusion_pytorch_model.fp16.safetensors",
                filename="wan2.7-t2v-1.3b-fp16.safetensors",
            ),
        },
        pip_dependencies=["diffusers", "torch", "transformers", "accelerate", "imageio-ffmpeg"],
        iris_module_path="models/video/",
        iris_class_name="Wan27Engine",
    ),

    "ltx23": ModelConfig(
        id="ltx23",
        name="LTX-2.3",
        type=ModelType.VIDEO,
        description="Lightricks LTX-2.3 — fast video generation",
        variants={
            "fp16": ModelVariant(
                name="LTX-2.3-FP16",
                quant="fp16",
                size_gb=9.2,
                min_vram_gb=12,
                min_ram_gb=16,
                download_url="https://huggingface.co/Lightricks/LTX-Video-2B/resolve/main/diffusion_pytorch_model.fp16.safetensors",
                filename="ltx-2.3-fp16.safetensors",
            ),
        },
        pip_dependencies=["diffusers", "torch", "transformers", "accelerate"],
        iris_module_path="models/video/",
        iris_class_name="LTX23Engine",
    ),

    # ─── 3D ASSETS ───
    "llama_mesh": ModelConfig(
        id="llama_mesh",
        name="LLaMA-Mesh",
        type=ModelType.THREE_D,
        description="LLaMA-Mesh — text-to-3D mesh generation",
        variants={
            "default": ModelVariant(
                name="LLaMA-Mesh",
                quant="fp16",
                size_gb=4.1,
                min_vram_gb=8,
                min_ram_gb=12,
                download_url="https://huggingface.co/omnilab/LLaMA-Mesh/resolve/main/model.safetensors",
                filename="llama-mesh.safetensors",
            ),
        },
        pip_dependencies=["transformers", "torch", "trimesh", "pygltflib"],
        iris_module_path="models/3d/",
        iris_class_name="LLaMAMeshEngine",
    ),

    "lgm": ModelConfig(
        id="lgm",
        name="LGM",
        type=ModelType.THREE_D,
        description="Large Gaussian Model — image-to-3D Gaussian splatting",
        variants={
            "default": ModelVariant(
                name="LGM",
                quant="fp16",
                size_gb=2.8,
                min_vram_gb=8,
                min_ram_gb=12,
                download_url="https://huggingface.co/ashawkey/LGM/resolve/main/model.safetensors",
                filename="lgm.safetensors",
            ),
        },
        pip_dependencies=["torch", "numpy", "imageio", "opencv-python"],
        iris_module_path="models/3d/",
        iris_class_name="LGMEngine",
    ),

    # ─── MOTION & ANIMATION ───
    "hy_motion": ModelConfig(
        id="hy_motion",
        name="HY-Motion-1.0",
        type=ModelType.MOTION,
        description="HY-Motion — text-to-motion/skeletal animation",
        variants={
            "default": ModelVariant(
                name="HY-Motion-1.0",
                quant="fp16",
                size_gb=1.2,
                min_vram_gb=4,
                min_ram_gb=8,
                download_url="https://huggingface.co/HYMotion/HY-Motion-1.0/resolve/main/model.safetensors",
                filename="hy-motion-1.0.safetensors",
            ),
        },
        pip_dependencies=["torch", "transformers", "numpy", "scipy"],
        iris_module_path="models/motion/",
        iris_class_name="HYMotionEngine",
    ),

    "mdm": ModelConfig(
        id="mdm",
        name="MDM",
        type=ModelType.MOTION,
        description="Motion Diffusion Model — human motion generation",
        variants={
            "default": ModelVariant(
                name="MDM",
                quant="fp32",
                size_gb=1.1,
                min_vram_gb=4,
                min_ram_gb=8,
                download_url="https://huggingface.co/GuyTevet/motion-diffusion-model/resolve/main/model.pt",
                filename="mdm.pt",
            ),
        },
        pip_dependencies=["torch", "numpy", "matplotlib", "tqdm"],
        iris_module_path="models/motion/",
        iris_class_name="MDMEngine",
    ),

    # ─── ROBOTICS ───
    "lerobot_pi0": ModelConfig(
        id="lerobot_pi0",
        name="LeRobot Pi0",
        type=ModelType.ROBOTICS,
        description="LeRobot Pi0 — vision-language-action for robotics",
        variants={
            "default": ModelVariant(
                name="Pi0",
                quant="fp32",
                size_gb=3.8,
                min_vram_gb=8,
                min_ram_gb=16,
                download_url="https://huggingface.co/lerobot/pi0/resolve/main/model.safetensors",
                filename="pi0.safetensors",
            ),
        },
        pip_dependencies=["lerobot", "torch", "transformers", "opencv-python"],
        iris_module_path="models/robotics/",
        iris_class_name="Pi0Engine",
    ),

    "smolvla": ModelConfig(
        id="smolvla",
        name="SmolVLA",
        type=ModelType.ROBOTICS,
        description="SmolVLA — lightweight vision-language-action",
        variants={
            "default": ModelVariant(
                name="SmolVLA",
                quant="fp16",
                size_gb=1.8,
                min_vram_gb=4,
                min_ram_gb=8,
                download_url="https://huggingface.co/merve/SmolVLA/resolve/main/model.safetensors",
                filename="smolvla.safetensors",
            ),
        },
        pip_dependencies=["transformers", "torch", "opencv-python"],
        iris_module_path="models/robotics/",
        iris_class_name="SmolVLAEngine",
    ),

    # ─── SCIENCE ───
    "alphafold3": ModelConfig(
        id="alphafold3",
        name="AlphaFold 3",
        type=ModelType.SCIENCE,
        description="AlphaFold 3 — protein structure prediction",
        variants={
            "default": ModelVariant(
                name="AlphaFold-3",
                quant="fp32",
                size_gb=4.5,
                min_vram_gb=16,
                min_ram_gb=32,
                download_url="https://huggingface.co/google/alphafold3/resolve/main/model.safetensors",
                filename="alphafold3.safetensors",
            ),
        },
        pip_dependencies=["alphafold", "jax", "jaxlib", "numpy", "biopython"],
        system_dependencies=["hmmer", "kalign"],
        iris_module_path="models/science/",
        iris_class_name="AlphaFold3Engine",
    ),

    "esmfold": ModelConfig(
        id="esmfold",
        name="ESMFold",
        type=ModelType.SCIENCE,
        description="Meta ESMFold — fast protein folding",
        variants={
            "default": ModelVariant(
                name="ESMFold",
                quant="fp32",
                size_gb=3.6,
                min_vram_gb=8,
                min_ram_gb=16,
                download_url="https://huggingface.co/facebook/esmfold_v1/resolve/main/pytorch_model.bin",
                filename="esmfold.bin",
            ),
        },
        pip_dependencies=["fair-esm", "biotite", "biopython"],
        iris_module_path="models/science/",
        iris_class_name="ESMFoldEngine",
    ),
}


def get_model_for_hardware(model_id: str, tier: str, vram_gb: float, ram_gb: float) -> Optional[ModelVariant]:
    """Select the best model variant for given hardware."""
    if model_id not in MODEL_REGISTRY:
        return None

    config = MODEL_REGISTRY[model_id]

    # Filter variants that fit in memory
    fitting = []
    for key, variant in config.variants.items():
        if vram_gb > 0:
            # GPU available - check VRAM
            if variant.min_vram_gb <= vram_gb * 0.9:
                fitting.append((key, variant))
        else:
            # CPU only - check RAM
            if variant.min_ram_gb <= ram_gb * 0.7:
                fitting.append((key, variant))

    if not fitting:
        return None

    # Sort by quality (prefer higher precision, then larger size)
    quant_order = {"fp32": 5, "fp16": 4, "q8": 3, "q5": 2, "q4": 1}
    fitting.sort(key=lambda x: (quant_order.get(x[1].quant, 0), x[1].size_gb), reverse=True)

    return fitting[0][1]


def list_all_models() -> List[str]:
    """List all available model IDs."""
    return list(MODEL_REGISTRY.keys())


def get_models_by_type(model_type: ModelType) -> Dict[str, ModelConfig]:
    """Get all models of a specific type."""
    return {k: v for k, v in MODEL_REGISTRY.items() if v.type == model_type}


if __name__ == "__main__":
    print("IRIS Model Registry")
    print("=" * 60)
    for model_id, config in MODEL_REGISTRY.items():
        print(f"\n{config.name} ({model_id})")
        print(f"  Type: {config.type.value}")
        print(f"  Description: {config.description}")
        print(f"  Variants: {len(config.variants)}")
        for vkey, variant in config.variants.items():
            print(f"    - {variant.name}: {variant.size_gb}GB (VRAM: {variant.min_vram_gb}GB, RAM: {variant.min_ram_gb}GB)")
