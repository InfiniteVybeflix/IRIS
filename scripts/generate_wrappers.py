#!/usr/bin/env python3
"""
IRIS Model Wrapper Templates — Auto-generated wrappers for each downloaded model.
These are placed in IRIS's models/ directory and provide a unified interface.
"""

from pathlib import Path
from typing import Dict

# Template for text models (LLMs)
TEXT_WRAPPER = """
"""IRIS {class_name} — {model_name} text generation wrapper."""
import os
import sys
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self.tokenizer = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the model into memory."""
        if self._loaded:
            return

        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=8192,
                n_threads=os.cpu_count() or 4,
                verbose=False,
            )
            self._loaded = True
            print(f"[{{self.__class__.__name__}}] Model loaded from {{self.model_path}}")
        except ImportError:
            # Fallback to transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                device_map="auto",
            )
            self._loaded = True

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7,
                 stop: List[str] = None, stream: bool = False) -> str:
        """Generate text from prompt."""
        if not self._loaded:
            self.load()

        if hasattr(self.model, 'create_completion'):
            # llama-cpp
            result = self.model.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or [],
                stream=stream,
            )
            if stream:
                return result  # Iterator
            return result['choices'][0]['text']
        else:
            # transformers
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
            )
            return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat format generation."""
        # Format messages into prompt
        prompt = self._format_chat(messages)
        return self.generate(prompt, **kwargs)

    def _format_chat(self, messages: List[Dict[str, str]]) -> str:
        """Format chat messages into a single prompt."""
        parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                parts.append(f"System: {{content}}")
            elif role == 'user':
                parts.append(f"User: {{content}}")
            elif role == 'assistant':
                parts.append(f"Assistant: {{content}}")
        parts.append("Assistant:")
        return "\n".join(parts)

    def unload(self):
        """Free model from memory."""
        self.model = None
        self.tokenizer = None
        self._loaded = False
        import gc
        gc.collect()
"""

# Template for image models
IMAGE_WRAPPER = """
"""IRIS {class_name} — {model_name} image generation wrapper."""
import os
from pathlib import Path
from typing import Optional, List, Union
import torch

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.pipe = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the diffusion pipeline."""
        if self._loaded:
            return

        from diffusers import StableDiffusionPipeline, DiffusionPipeline

        # Auto-detect pipeline type
        if "flux" in self.model_path.lower():
            self.pipe = DiffusionPipeline.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
        else:
            self.pipe = StableDiffusionPipeline.from_single_file(
                self.model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )

        if torch.cuda.is_available():
            self.pipe = self.pipe.to("cuda")
        elif torch.backends.mps.is_available():
            self.pipe = self.pipe.to("mps")

        self._loaded = True
        print(f"[{{self.__class__.__name__}}] Pipeline loaded")

    def generate(self, prompt: str, negative_prompt: str = "",
                 width: int = 512, height: int = 512,
                 steps: int = 30, guidance: float = 7.5,
                 seed: Optional[int] = None) -> str:
        """Generate image from text prompt. Returns path to saved image."""
        if not self._loaded:
            self.load()

        generator = torch.Generator(device=self.pipe.device)
        if seed is not None:
            generator.manual_seed(seed)

        result = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=generator,
        )

        # Save image
        output_dir = Path("outputs/images")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.png"
        result.images[0].save(output_path)

        return str(output_path)

    def generate_variations(self, image_path: str, prompt: str = "",
                           strength: float = 0.75, **kwargs) -> str:
        """Generate variations of an existing image."""
        if not self._loaded:
            self.load()

        from PIL import Image
        init_image = Image.open(image_path).convert("RGB")

        result = self.pipe(
            prompt=prompt,
            image=init_image,
            strength=strength,
            **kwargs
        )

        output_dir = Path("outputs/images")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_var_{{int(time.time())}}.png"
        result.images[0].save(output_path)

        return str(output_path)

    def unload(self):
        """Free pipeline from memory."""
        self.pipe = None
        self._loaded = False
        import gc
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
"""

# Template for audio models
AUDIO_WRAPPER = """
"""IRIS {class_name} — {model_name} audio generation wrapper."""
import os
from pathlib import Path
from typing import Optional, List
import torch

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the audio model."""
        if self._loaded:
            return

        # Model-specific loading
        self._load_impl()
        self._loaded = True
        print(f"[{{self.__class__.__name__}}] Audio model loaded")

    def _load_impl(self):
        """Override in subclass for specific model loading."""
        pass

    def generate(self, prompt: str, duration: int = 10, **kwargs) -> str:
        """Generate audio from text. Returns path to saved audio."""
        if not self._loaded:
            self.load()

        output_dir = Path("outputs/audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.wav"

        # Model-specific generation
        audio = self._generate_impl(prompt, duration, **kwargs)

        # Save
        import scipy.io.wavfile as wav
        wav.write(str(output_path), rate=32000, data=audio)

        return str(output_path)

    def _generate_impl(self, prompt: str, duration: int, **kwargs):
        """Override in subclass."""
        raise NotImplementedError

    def clone_voice(self, reference_audio: str, text: str, **kwargs) -> str:
        """Clone voice from reference audio."""
        raise NotImplementedError("Voice cloning not supported by this model")

    def unload(self):
        """Free model from memory."""
        self.model = None
        self._loaded = False
        import gc
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
"""

# Template for video models
VIDEO_WRAPPER = """
"""IRIS {class_name} — {model_name} video generation wrapper."""
import os
from pathlib import Path
from typing import Optional, List
import torch

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.pipe = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the video generation pipeline."""
        if self._loaded:
            return

        from diffusers import DiffusionPipeline

        self.pipe = DiffusionPipeline.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )

        if torch.cuda.is_available():
            self.pipe = self.pipe.to("cuda")

        self._loaded = True
        print(f"[{{self.__class__.__name__}}] Video pipeline loaded")

    def generate(self, prompt: str, num_frames: int = 16, width: int = 512,
                 height: int = 512, fps: int = 8, **kwargs) -> str:
        """Generate video from text. Returns path to saved video."""
        if not self._loaded:
            self.load()

        result = self.pipe(
            prompt=prompt,
            num_frames=num_frames,
            width=width,
            height=height,
            **kwargs
        )

        output_dir = Path("outputs/video")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.mp4"

        # Export frames to video
        import imageio
        frames = [f for f in result.frames[0]]
        imageio.mimsave(str(output_path), frames, fps=fps)

        return str(output_path)

    def unload(self):
        """Free pipeline from memory."""
        self.pipe = None
        self._loaded = False
        import gc
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
"""

# Template for 3D models
THREE_D_WRAPPER = """
"""IRIS {class_name} — {model_name} 3D generation wrapper."""
import os
from pathlib import Path
from typing import Optional, List, Tuple
import torch
import numpy as np

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the 3D generation model."""
        if self._loaded:
            return

        # Model-specific loading
        self._load_impl()
        self._loaded = True
        print(f"[{{self.__class__.__name__}}] 3D model loaded")

    def _load_impl(self):
        """Override in subclass."""
        pass

    def generate_mesh(self, prompt: str, **kwargs) -> str:
        """Generate 3D mesh from text. Returns path to .obj file."""
        if not self._loaded:
            self.load()

        output_dir = Path("outputs/3d")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.obj"

        vertices, faces = self._generate_mesh_impl(prompt, **kwargs)
        self._save_obj(vertices, faces, output_path)

        return str(output_path)

    def generate_from_image(self, image_path: str, **kwargs) -> str:
        """Generate 3D from image."""
        raise NotImplementedError

    def _generate_mesh_impl(self, prompt: str, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Override in subclass. Returns (vertices, faces)."""
        raise NotImplementedError

    def _save_obj(self, vertices: np.ndarray, faces: np.ndarray, path: Path):
        """Save mesh as OBJ file."""
        with open(path, 'w') as f:
            for v in vertices:
                f.write(f"v {{v[0]}} {{v[1]}} {{v[2]}}\n")
            for face in faces:
                f.write(f"f {{face[0]+1}} {{face[1]+1}} {{face[2]+1}}\n")

    def unload(self):
        """Free model from memory."""
        self.model = None
        self._loaded = False
        import gc
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
"""

# Template for motion models
MOTION_WRAPPER = """
"""IRIS {class_name} — {model_name} motion generation wrapper."""
import os
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the motion model."""
        if self._loaded:
            return
        self._load_impl()
        self._loaded = True
        print(f"[{{self.__class__.__name__}}] Motion model loaded")

    def _load_impl(self):
        """Override in subclass."""
        pass

    def generate_motion(self, prompt: str, duration_seconds: float = 5.0,
                       fps: int = 30, **kwargs) -> str:
        """Generate motion from text. Returns path to .bvh or .fbx file."""
        if not self._loaded:
            self.load()

        output_dir = Path("outputs/motion")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.bvh"

        motion_data = self._generate_impl(prompt, duration_seconds, fps, **kwargs)
        self._save_bvh(motion_data, output_path, fps)

        return str(output_path)

    def _generate_impl(self, prompt: str, duration: float, fps: int, **kwargs) -> np.ndarray:
        """Override in subclass. Returns motion array (frames x joints x 3)."""
        raise NotImplementedError

    def _save_bvh(self, motion_data: np.ndarray, path: Path, fps: int):
        """Save motion as BVH file."""
        # Simplified BVH export
        with open(path, 'w') as f:
            f.write("HIERARCHY\n")
            f.write("ROOT Hips\n")
            f.write("{\n")
            f.write("  OFFSET 0.0 0.0 0.0\n")
            f.write("  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")
            f.write("}\n")
            f.write("MOTION\n")
            f.write(f"Frames: {{len(motion_data)}}\n")
            f.write(f"Frame Time: {{1.0/fps}}\n")
            for frame in motion_data:
                f.write(" ".join(f"{{v:.6f}}" for v in frame.flatten()) + "\n")

    def unload(self):
        self.model = None
        self._loaded = False
        import gc
        gc.collect()
"""

# Template for robotics models
ROBOTICS_WRAPPER = """
"""IRIS {class_name} — {model_name} robotics VLA wrapper."""
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np
import torch

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self.processor = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the VLA model."""
        if self._loaded:
            return

        from transformers import AutoModelForVision2Seq, AutoProcessor
        self.processor = AutoProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForVision2Seq.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        if torch.cuda.is_available():
            self.model = self.model.to("cuda")

        self._loaded = True
        print(f"[{{self.__class__.__name__}}] VLA model loaded")

    def predict_action(self, image: np.ndarray, instruction: str,
                      **kwargs) -> Dict[str, Any]:
        """Predict robot action from image + instruction."""
        if not self._loaded:
            self.load()

        inputs = self.processor(images=image, text=instruction, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {{k: v.cuda() for k, v in inputs.items()}}

        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=100)

        action_text = self.processor.decode(outputs[0], skip_special_tokens=True)

        # Parse action (model-specific)
        return self._parse_action(action_text)

    def _parse_action(self, action_text: str) -> Dict[str, Any]:
        """Parse model output into robot action."""
        # Default: return as-is, subclass can override
        return {{"raw": action_text, "parsed": None}}

    def unload(self):
        self.model = None
        self.processor = None
        self._loaded = False
        import gc
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
"""

# Template for science models
SCIENCE_WRAPPER = """
"""IRIS {class_name} — {model_name} scientific computation wrapper."""
import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import numpy as np

class {class_name}:
    """
    {description}

    Hardware-optimized for: {tier}
    Quantization: {quant}
    """

    def __init__(self, model_path: str = None, iris_core=None):
        self.iris_core = iris_core
        self.model_path = model_path or self._default_path()
        self.model = None
        self._loaded = False

    def _default_path(self) -> str:
        return str(Path(__file__).parent / "{filename}")

    def load(self):
        """Load the scientific model."""
        if self._loaded:
            return
        self._load_impl()
        self._loaded = True
        print(f"[{{self.__class__.__name__}}] Science model loaded")

    def _load_impl(self):
        """Override in subclass."""
        pass

    def predict_structure(self, sequence: str, **kwargs) -> str:
        """Predict molecular/protein structure. Returns path to result file."""
        if not self._loaded:
            self.load()

        output_dir = Path("outputs/science")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{{self.__class__.__name__.lower()}}_{{int(time.time())}}.pdb"

        result = self._predict_impl(sequence, **kwargs)
        self._save_result(result, output_path)

        return str(output_path)

    def _predict_impl(self, sequence: str, **kwargs):
        """Override in subclass."""
        raise NotImplementedError

    def _save_result(self, result, path: Path):
        """Save prediction result."""
        with open(path, 'w') as f:
            f.write(str(result))

    def unload(self):
        self.model = None
        self._loaded = False
        import gc
        gc.collect()


# Map model types to wrapper templates
WRAPPER_TEMPLATES = {
    "text": TEXT_WRAPPER,
    "image": IMAGE_WRAPPER,
    "audio": AUDIO_WRAPPER,
    "video": VIDEO_WRAPPER,
    "3d": THREE_D_WRAPPER,
    "motion": MOTION_WRAPPER,
    "robotics": ROBOTICS_WRAPPER,
    "science": SCIENCE_WRAPPER,
}


def generate_wrapper(model_id: str, output_dir: str = "models") -> str:
    """Generate a wrapper file for a model."""
    from model_registry import MODEL_REGISTRY

    if model_id not in MODEL_REGISTRY:
        raise ValueError(f"Model {model_id} not found")

    config = MODEL_REGISTRY[model_id]
    template = WRAPPER_TEMPLATES.get(config.type.value, TEXT_WRAPPER)

    # Get first variant for defaults
    variant = list(config.variants.values())[0]

    # Fill template
    wrapper_code = template.format(
        class_name=config.iris_class_name,
        model_name=config.name,
        description=config.description,
        tier="all",
        quant=variant.quant,
        filename=variant.filename,
    )

    # Write to file
    output_path = Path(output_dir) / config.type.value / f"{model_id}_wrapper.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(wrapper_code)

    return str(output_path)


def generate_all_wrappers(output_dir: str = "models") -> List[str]:
    """Generate wrappers for all registered models."""
    from model_registry import MODEL_REGISTRY

    generated = []
    for model_id in MODEL_REGISTRY:
        path = generate_wrapper(model_id, output_dir)
        generated.append(path)
        print(f"Generated: {path}")

    return generated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Generate wrapper for specific model")
    parser.add_argument("--all", action="store_true", help="Generate all wrappers")
    parser.add_argument("--output-dir", default="models", help="Output directory")
    args = parser.parse_args()

    if args.all:
        generate_all_wrappers(args.output_dir)
    elif args.model:
        path = generate_wrapper(args.model, args.output_dir)
        print(f"Generated: {path}")
    else:
        parser.print_help()
