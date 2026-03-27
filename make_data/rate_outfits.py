from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from openpyxl import load_workbook


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
WORKBOOK_PATH = PROJECT_DIR / "data.xlsx"
ITEM_PICS_DIR = PROJECT_DIR / "item_pics"
CACHE_DIR = APP_DIR / ".image_cache"
DISPLAY_MAX_SIZE = 480
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CACHE_VERSION = "qlmanage-v1"


@dataclass(frozen=True)
class OutfitSample:
    top_id: int
    bottom_id: int
    temperature: int


def load_item_ids_by_type() -> tuple[list[int], list[int]]:
    workbook = load_workbook(WORKBOOK_PATH, data_only=True)
    try:
        if "metadata" not in workbook.sheetnames:
            raise ValueError(f"Missing 'metadata' sheet in {WORKBOOK_PATH.name}.")

        sheet = workbook["metadata"]
        top_ids: list[int] = []
        bottom_ids: list[int] = []

        for item_id, _, _, _, item_type, *_ in sheet.iter_rows(min_row=2, values_only=True):
            if item_id is None or item_type is None:
                continue

            item_id = int(item_id)
            item_path = ITEM_PICS_DIR / f"{item_id}.png"
            if not item_path.exists():
                raise FileNotFoundError(f"Missing image for item {item_id}: {item_path}")

            normalized_type = str(item_type).strip().lower()
            if normalized_type == "top":
                top_ids.append(item_id)
            elif normalized_type == "bottom":
                bottom_ids.append(item_id)

        if not top_ids or not bottom_ids:
            raise ValueError("Metadata does not contain both top and bottom items.")

        return top_ids, bottom_ids
    finally:
        workbook.close()


def is_real_png(path: Path) -> bool:
    with path.open("rb") as image_file:
        return image_file.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE


def cache_metadata_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".meta")


def has_current_cache(cache_path: Path, source_path: Path) -> bool:
    metadata_path = cache_metadata_path(cache_path)
    if not cache_path.exists() or not metadata_path.exists():
        return False

    expected_lines = [
        f"version={CACHE_VERSION}",
        f"source_mtime_ns={source_path.stat().st_mtime_ns}",
    ]

    try:
        actual_lines = metadata_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    return actual_lines == expected_lines


def write_cache_metadata(cache_path: Path, source_path: Path) -> None:
    metadata_path = cache_metadata_path(cache_path)
    metadata_path.write_text(
        f"version={CACHE_VERSION}\nsource_mtime_ns={source_path.stat().st_mtime_ns}\n",
        encoding="utf-8",
    )


def generate_quicklook_png(source_path: Path, cache_path: Path) -> bool:
    qlmanage_path = shutil.which("qlmanage")
    if not qlmanage_path:
        return False

    with tempfile.TemporaryDirectory(dir=CACHE_DIR) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        command = [
            qlmanage_path,
            "-t",
            "-s",
            str(DISPLAY_MAX_SIZE),
            "-o",
            str(temp_dir),
            str(source_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return False

        generated_files = list(temp_dir.glob("*.png"))
        if len(generated_files) != 1:
            return False

        os.replace(generated_files[0], cache_path)
        write_cache_metadata(cache_path, source_path)
        return True


def generate_sips_png(source_path: Path, cache_path: Path) -> bool:
    sips_path = shutil.which("sips")
    if not sips_path:
        return False

    command = [
        sips_path,
        "-s",
        "format",
        "png",
        "-Z",
        str(DISPLAY_MAX_SIZE),
        str(source_path),
        "--out",
        str(cache_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return False

    write_cache_metadata(cache_path, source_path)
    return True


def prepare_display_image(item_id: int) -> Path:
    source_path = ITEM_PICS_DIR / f"{item_id}.png"
    cache_path = CACHE_DIR / f"{item_id}.png"

    if is_real_png(source_path):
        return source_path

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if has_current_cache(cache_path, source_path):
        return cache_path

    if generate_quicklook_png(source_path, cache_path):
        return cache_path

    if generate_sips_png(source_path, cache_path):
        return cache_path

    raise RuntimeError(
        f"Unable to create a display image for item {item_id}. "
        "This app needs macOS Quick Look or sips to render the HEIF-based images in item_pics."
    )


def append_score(sample: OutfitSample, score: int) -> None:
    workbook = load_workbook(WORKBOOK_PATH)
    try:
        if "data" not in workbook.sheetnames:
            raise ValueError(f"Missing 'data' sheet in {WORKBOOK_PATH.name}.")

        sheet = workbook["data"]
        sheet.append([sample.top_id, sample.bottom_id, sample.temperature, score])
        workbook.save(WORKBOOK_PATH)
    finally:
        workbook.close()


class OutfitRaterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Outfit Training Data")
        self.root.minsize(1100, 700)

        self.top_ids, self.bottom_ids = load_item_ids_by_type()
        self.current_sample: OutfitSample | None = None
        self.top_photo: tk.PhotoImage | None = None
        self.bottom_photo: tk.PhotoImage | None = None

        self.info_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a score from 1 to 10. Press 0 for score 10.")

        self.build_ui()
        self.bind_shortcuts()
        self.load_next_sample()

    def build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(
            container,
            text="Rate Random Outfit Combinations",
            font=("Helvetica", 20, "bold"),
        )
        title.pack(anchor="center", pady=(0, 6))

        info_label = ttk.Label(container, textvariable=self.info_var, font=("Helvetica", 13))
        info_label.pack(anchor="center", pady=(0, 12))

        images_frame = ttk.Frame(container)
        images_frame.pack(fill="both", expand=True)
        images_frame.columnconfigure(0, weight=1)
        images_frame.columnconfigure(1, weight=1)

        self.top_image_label = self.build_image_panel(images_frame, 0, "Top")
        self.bottom_image_label = self.build_image_panel(images_frame, 1, "Bottom")

        controls = ttk.Frame(container, padding=(0, 16, 0, 0))
        controls.pack(fill="x")

        instructions = ttk.Label(
            controls,
            text="Score the outfit from 1 to 10. After each score, the row is appended to data.xlsx.",
        )
        instructions.pack(anchor="center", pady=(0, 10))

        buttons_frame = ttk.Frame(controls)
        buttons_frame.pack(anchor="center")

        for score in range(1, 11):
            label = str(score)
            if score == 10:
                label = "10 (0)"

            button = ttk.Button(
                buttons_frame,
                text=label,
                command=lambda selected=score: self.save_score(selected),
                width=8,
            )
            button.grid(row=0, column=score - 1, padx=4, pady=4)

        footer = ttk.Frame(container, padding=(0, 12, 0, 0))
        footer.pack(fill="x")

        status_label = ttk.Label(footer, textvariable=self.status_var, foreground="#1f3b4d")
        status_label.pack(side="left")

        refresh_button = ttk.Button(footer, text="Skip / New Random Outfit", command=self.load_next_sample)
        refresh_button.pack(side="right")

    def build_image_panel(self, parent: ttk.Frame, column: int, label_text: str) -> ttk.Label:
        panel = ttk.Frame(parent, padding=12)
        panel.grid(row=0, column=column, sticky="nsew")

        heading = ttk.Label(panel, text=label_text, font=("Helvetica", 16, "bold"))
        heading.pack(anchor="center", pady=(0, 10))

        image_label = ttk.Label(panel)
        image_label.pack(anchor="center", expand=True)
        return image_label

    def bind_shortcuts(self) -> None:
        for score in range(1, 10):
            self.root.bind(f"<KeyPress-{score}>", lambda _event, selected=score: self.save_score(selected))
        self.root.bind("<KeyPress-0>", lambda _event: self.save_score(10))
        self.root.bind("<space>", lambda _event: self.load_next_sample())

    def load_next_sample(self, status_message: str | None = None) -> None:
        sample = OutfitSample(
            top_id=random.choice(self.top_ids),
            bottom_id=random.choice(self.bottom_ids),
            temperature=random.randint(20, 90),
        )

        try:
            self.top_photo = self.load_photo(sample.top_id)
            self.bottom_photo = self.load_photo(sample.bottom_id)
        except Exception as exc:
            messagebox.showerror("Image Error", str(exc), parent=self.root)
            return

        self.current_sample = sample
        self.top_image_label.configure(image=self.top_photo)
        self.bottom_image_label.configure(image=self.bottom_photo)
        self.info_var.set(
            f"Top #{sample.top_id}    Bottom #{sample.bottom_id}    Outside Temperature: {sample.temperature}F"
        )
        self.status_var.set(status_message or "Choose a score from 1 to 10. Press 0 for score 10.")

    def load_photo(self, item_id: int) -> tk.PhotoImage:
        image_path = prepare_display_image(item_id)
        photo = tk.PhotoImage(file=str(image_path))

        longest_side = max(photo.width(), photo.height())
        if longest_side > DISPLAY_MAX_SIZE:
            scale = math.ceil(longest_side / DISPLAY_MAX_SIZE)
            photo = photo.subsample(scale, scale)

        return photo

    def save_score(self, score: int) -> None:
        if self.current_sample is None:
            return

        try:
            append_score(self.current_sample, score)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=self.root)
            return

        saved_sample = self.current_sample
        status_message = (
            f"Saved row: top #{saved_sample.top_id}, bottom #{saved_sample.bottom_id}, "
            f"{saved_sample.temperature}F, score {score}."
        )
        self.load_next_sample(status_message=status_message)


def run_check() -> int:
    top_ids, bottom_ids = load_item_ids_by_type()
    sample = OutfitSample(
        top_id=random.choice(top_ids),
        bottom_id=random.choice(bottom_ids),
        temperature=random.randint(20, 90),
    )
    top_image = prepare_display_image(sample.top_id)
    bottom_image = prepare_display_image(sample.bottom_id)
    print(f"Loaded {len(top_ids)} tops and {len(bottom_ids)} bottoms.")
    print(
        f"Sample ok: top #{sample.top_id} ({top_image.name}), "
        f"bottom #{sample.bottom_id} ({bottom_image.name}), temp {sample.temperature}F"
    )
    return 0


def main() -> int:
    random.seed(time.time_ns())

    if "--check" in sys.argv:
        return run_check()

    root = tk.Tk()
    try:
        OutfitRaterApp(root)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror("Startup Error", str(exc), parent=root)
        root.destroy()
        return 1

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
