"""Chrome driver setup plus a small step recorder that turns screenshots into a video."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

log = logging.getLogger("webbot")


def make_driver(headless: bool = True, width: int = 1280, height: int = 800) -> webdriver.Chrome:
    """Start Chrome. Selenium Manager downloads a matching driver automatically."""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={width},{height}")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--blink-settings=imagesEnabled=true")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(45)
    return driver


def wait(driver, seconds: float = 15) -> WebDriverWait:
    return WebDriverWait(driver, seconds)


def _font() -> str:
    """Point ffmpeg at a real font file when one is known (Windows), else use its default."""
    for f in (Path("C:/Windows/Fonts/segoeui.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if f.exists():
            return ":fontfile='" + f.as_posix().replace(":", "\\:") + "'"
    return ""


class Recorder:
    """Saves a captioned screenshot for each step; `to_video` stitches them with ffmpeg."""

    def __init__(self, driver, folder: Path, enabled: bool = True):
        self.driver = driver
        self.folder = folder
        self.enabled = enabled
        self.frames: list[tuple[Path, str]] = []
        if enabled:
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("step_*.png"):
                old.unlink()

    def shot(self, caption: str):
        if not self.enabled:
            return
        path = self.folder / f"step_{len(self.frames):03d}.png"
        self.driver.save_screenshot(str(path))
        self.frames.append((path, caption))
        log.info("  [frame] %s", caption)

    def to_video(self, out_mp4: Path, seconds_per_frame: float = 1.6) -> Path | None:
        """Build an MP4 (and a GIF next to it) with each step's caption burned in."""
        if not self.enabled or not self.frames:
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            log.warning("ffmpeg not found; screenshots are in %s", self.folder)
            return None
        # Write captions to files so any characters are safe for ffmpeg's drawtext.
        parts = []
        for i, (png, caption) in enumerate(self.frames):
            txt = self.folder / f"cap_{i:03d}.txt"
            txt.write_text(caption, encoding="utf-8")
            clip = self.folder / f"clip_{i:03d}.mp4"
            vf = ("scale=1280:-2,pad=1280:ih+70:0:0:color=0x111827,"
                  f"drawtext=textfile='{txt.as_posix().replace(':', chr(92) + ':')}':"
                  f"fontcolor=white:fontsize=30:x=(w-text_w)/2:y=h-50{_font()}")
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-t", str(seconds_per_frame),
                            "-i", str(png), "-vf", vf, "-r", "25", "-pix_fmt", "yuv420p", str(clip)], check=True)
            parts.append(clip)
        listing = self.folder / "clips.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(out_mp4)], check=True)
        gif = out_mp4.with_suffix(".gif")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(out_mp4), "-vf",
                        "fps=6,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse",
                        str(gif)], check=True)
        for p in parts + [listing] + list(self.folder.glob("cap_*.txt")):
            p.unlink(missing_ok=True)
        return out_mp4
