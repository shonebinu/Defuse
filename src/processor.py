import io
from typing import List, Optional

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


class ImageProcessor:
    isnet_model_path = (
        "/app/share/io.github.shonebinu.Defuse/models/isnet-general-use.onnx"
    )

    def __init__(self):
        self.onnx_session: Optional[ort.InferenceSession] = None
        self.current_provider: Optional[str] = None

    def get_supported_mimes(self) -> List[str]:
        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

        return [f"image/{ext[1:]}" for ext in supported_extensions]

    def run_model(self, img_bytes: bytes, output_format: str) -> bytes:
        if self.onnx_session is None:
            raise RuntimeError("ONNX session is not initialized.")

        # https://github.com/danielgatis/rembg/blob/main/rembg/sessions/dis_general_use.py

        img = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes)).convert("RGB"))

        mean, std, size = 0.5, 1.0, (1024, 1024)

        arr = np.array(img.resize(size, Image.Resampling.LANCZOS)).astype(np.float32)
        img_input = ((arr / max(arr.max(), 1e-6) - mean) / std).transpose(2, 0, 1)

        out = self.onnx_session.run(
            None,
            {self.onnx_session.get_inputs()[0].name: img_input[None]},  # type: ignore
        )[0][0, 0]

        ma, mi = out.max(), out.min()
        mask = Image.fromarray(
            ((out - mi) / max((ma - mi), 1e-6) * 255).astype("uint8"), "L"
        ).resize(img.size, Image.Resampling.LANCZOS)

        bio = io.BytesIO()
        Image.composite(img.convert("RGBA"), Image.new("RGBA", img.size, 0), mask).save(
            bio, format=output_format
        )
        return bio.getvalue()

    def remove_bg(self, img_bytes: bytes, output_format="PNG") -> bytes:
        if not self.onnx_session:
            # webgpu(default) and cpu in x64 and cpu only in arm
            self.onnx_session = ort.InferenceSession(
                self.isnet_model_path, providers=ort.get_available_providers()
            )
            self.current_provider = self.onnx_session.get_providers()[0]

        try:
            return self.run_model(img_bytes, output_format)
        except Exception:
            if self.current_provider == "CPUExecutionProvider":
                raise

            print(f"Falling back to CPUExecutionProvider from {self.current_provider}")

            self.current_provider = "CPUExecutionProvider"
            self.onnx_session = ort.InferenceSession(
                self.isnet_model_path, providers=["CPUExecutionProvider"]
            )

            return self.run_model(img_bytes, output_format)
