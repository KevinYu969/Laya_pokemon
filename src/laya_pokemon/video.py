"""串流錄影，避免將整段影片保留在記憶體。"""
from __future__ import annotations

from pathlib import Path


class VideoRecorder:
    def __init__(self, path: Path, fps: int = 30, scale: int = 3):
        import imageio.v2 as imageio
        if fps <= 0 or scale < 1:
            raise ValueError("fps 與 scale 必須為正值")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.fps, self.scale, self.frames = path, fps, scale, 0
        self.writer = imageio.get_writer(str(path), fps=fps, codec="libx264", pixelformat="yuv420p", macro_block_size=1)

    def append(self, frame) -> None:
        import numpy as np
        from PIL import Image
        rgb = np.asarray(frame)[..., :3].astype("uint8")
        if self.scale != 1:
            image = Image.fromarray(rgb)
            rgb = np.asarray(image.resize((image.width * self.scale, image.height * self.scale), Image.Resampling.NEAREST))
        self.writer.append_data(rgb)
        self.frames += 1

    def close(self) -> dict:
        self.writer.close()
        return {"filename": self.path.name, "fps": self.fps, "frames": self.frames,
                "playback_seconds": self.frames / self.fps, "timing": "emulated_time", "audio": False}


def recording_smoke(path: Path) -> dict:
    import numpy as np
    from PIL import Image, ImageDraw
    recorder = VideoRecorder(path, fps=30, scale=1)
    try:
        for index in range(60):
            image = Image.new("RGB", (480, 432), "#102239")
            draw = ImageDraw.Draw(image)
            draw.text((24, 24), "RECORDING PIPELINE TEST", fill="white")
            draw.text((24, 48), "NO GAMEPLAY / 2 SECONDS / 30 FPS", fill="white")
            x = 24 + index * 6
            draw.rectangle((x, 180, x + 36, 216), fill="#42c5a1")
            recorder.append(np.asarray(image))
    finally:
        result = recorder.close()
    return {"kind": "recording_pipeline_smoke_not_gameplay", **result}

