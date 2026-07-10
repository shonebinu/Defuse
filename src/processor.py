import io
from typing import List, Optional

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


class ImageProcessor:
    isnet_model_path = (
        "/app/share/io.github.shonebinu.Defuse/models/isnet-general-use.onnx"
    )
    onnx_session: Optional[ort.InferenceSession] = None
    current_provider: Optional[str] = None

    @staticmethod
    def get_supported_mimes() -> List[str]:
        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

        return [f"image/{ext[1:]}" for ext in supported_extensions]

    @staticmethod
    def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
        with io.BytesIO() as buf:
            image.save(buf, format=format)
            return buf.getvalue()

    @classmethod
    def run_model(cls, image: Image.Image) -> Image.Image:
        if cls.onnx_session is None:
            raise RuntimeError("ONNX session is not initialized.")

        # https://github.com/danielgatis/rembg/blob/main/rembg/sessions/dis_general_use.py

        img = ImageOps.exif_transpose(image)

        if img.mode != "RGB":
            img = img.convert("RGB")

        mean, std, size = 0.5, 1.0, (1024, 1024)

        arr = np.array(img.resize(size, Image.Resampling.LANCZOS)).astype(np.float32)
        img_input = ((arr / max(arr.max(), 1e-6) - mean) / std).transpose(2, 0, 1)

        out = cls.onnx_session.run(
            None,
            {cls.onnx_session.get_inputs()[0].name: img_input[None]},  # type: ignore
        )[0][0, 0]

        ma, mi = out.max(), out.min()
        mask = Image.fromarray(
            ((out - mi) / max((ma - mi), 1e-6) * 255).astype("uint8"), "L"
        ).resize(img.size, Image.Resampling.LANCZOS)

        return Image.composite(
            img.convert("RGBA"), Image.new("RGBA", img.size, 0), mask
        )

    @classmethod
    def remove_bg(cls, image: Image.Image) -> Image.Image:
        if not cls.onnx_session:
            # webgpu(default) and cpu in x64 and cpu only in arm
            cls.onnx_session = ort.InferenceSession(
                cls.isnet_model_path, providers=ort.get_available_providers()
            )
            cls.current_provider = cls.onnx_session.get_providers()[0]

        try:
            return cls.run_model(image)
        except Exception:
            if cls.current_provider == "CPUExecutionProvider":
                raise

            print(f"Falling back to CPUExecutionProvider from {cls.current_provider}")

            cls.current_provider = "CPUExecutionProvider"
            cls.onnx_session = ort.InferenceSession(
                cls.isnet_model_path, providers=["CPUExecutionProvider"]
            )

            return cls.run_model(image)
