import io
from typing import List

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


class ImageProcessor:
    isnet_model_path = (
        "/app/share/io.github.shonebinu.Defuse/models/isnet-general-use.onnx"
    )

    def __init__(self):
        self.onnx_session = None

    def ensure_session(self):
        if self.onnx_session is None:
            # webgpu provider on x86 and cpu on aarch64
            self.onnx_session = ort.InferenceSession(
                self.isnet_model_path, providers=ort.get_available_providers()
            )

    def get_supported_mimes(self) -> List[str]:
        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

        return [f"image/{ext[1:]}" for ext in supported_extensions]

    def remove_bg(self, img_bytes: bytes, output_format="PNG") -> bytes:
        # https://github.com/danielgatis/rembg/blob/main/rembg/sessions/dis_general_use.py
        self.ensure_session()

        img = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes)).convert("RGB"))

        mean, std, size = 0.5, 1.0, (1024, 1024)

        arr = np.array(img.resize(size, Image.Resampling.LANCZOS)).astype(np.float32)
        img_input = ((arr / max(arr.max(), 1e-6) - mean) / std).transpose(2, 0, 1)

        out = self.onnx_session.run(  # type: ignore
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
