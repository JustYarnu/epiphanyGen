"""Generate a filtered, captioned epiphany image and its attribution sidecar."""

from __future__ import annotations

import argparse
import io
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

try:
	from .caption_generator import generate_caption
	from .img_grabber import ImageResult, fetch_configured_image, fetch_random_image
except ImportError:  # Allows ``python generator/epiphany_generator.py``.
	from caption_generator import generate_caption
	from img_grabber import ImageResult, fetch_configured_image, fetch_random_image


DEFAULT_FONT = r"C:\Windows\Fonts\impact.ttf"
LOGGER = logging.getLogger(__name__)


def configure_logging(project_root: str | Path) -> None:
	"""Append generation events to the project's separate debug log."""
	log_path = Path(project_root) / "debug" / "generator.log"
	log_path.parent.mkdir(parents=True, exist_ok=True)
	if not LOGGER.handlers:
		handler = logging.FileHandler(log_path, encoding="utf-8")
		handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
		LOGGER.addHandler(handler)
		LOGGER.setLevel(logging.INFO)


@dataclass(frozen=True)
class EpiphanyResult:
	"""Final image, caption, and source attribution produced by the generator."""
	image: Image.Image
	caption: str
	attribution_markdown: str

	def save(self, path: str | Path) -> Path:
		"""Save the rendered image and matching attribution Markdown sidecar."""
		path = Path(path)
		path.parent.mkdir(parents=True, exist_ok=True)
		self.image.save(path)
		path.with_suffix(".md").write_text(self.attribution_markdown + "\n", encoding="utf-8")
		return path


def load_generation_settings(path: str | Path) -> dict[str, Any]:
	"""Read image-generation settings from the project's simple YAML format."""
	settings: dict[str, Any] = {
		"width": 1080,
		"height": 1080,
		"font_path": DEFAULT_FONT,
		"pixel_block_size": 5,
		"noise_amount": 18,
		"output_path": "output/epiphany.png",
		"fully_random": False,
	}
	reading_resolution = False

	for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
		line = raw_line.split("#", 1)[0].strip()
		if not line:
			continue
		if line.startswith("output_resolution"):
			reading_resolution = True
			continue
		if reading_resolution and line.startswith("width"):
			settings["width"] = int(line.split(":", 1)[1].strip())
			continue
		if reading_resolution and line.startswith("height"):
			settings["height"] = int(line.split(":", 1)[1].strip())
			continue
		if line.startswith("font_path"):
			settings["font_path"] = line.split(":", 1)[1].strip().strip("'\"")
			reading_resolution = False
			continue
		if line.startswith("fully_random"):
			value = line.partition(":")[2].strip().lower()
			if value not in {"true", "false"}:
				raise ValueError("fully_random must be true or false")
			settings["fully_random"] = value == "true"
			reading_resolution = False
			continue
		if line.startswith("pixel_block_size"):
			settings["pixel_block_size"] = int(line.split(":", 1)[1].strip())
			reading_resolution = False
			continue
		if line.startswith("noise_amount"):
			settings["noise_amount"] = float(line.split(":", 1)[1].strip())
			reading_resolution = False
			continue
		if line.startswith("output_path"):
			settings["output_path"] = line.split(":", 1)[1].strip().strip("'\"")
			reading_resolution = False
			continue
		if reading_resolution and not raw_line.startswith((" ", "\t")):
			reading_resolution = False

	if settings["width"] < 1 or settings["height"] < 1:
		raise ValueError("output resolution must be positive")
	if settings["pixel_block_size"] < 1:
		raise ValueError("pixel_block_size must be positive")
	if settings["noise_amount"] < 0:
		raise ValueError("noise_amount cannot be negative")
	return settings


def resize_to_resolution(image: Image.Image, width: int, height: int) -> Image.Image:
	"""Resize and center-crop an image to the exact configured dimensions."""
	return ImageOps.fit(image.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)


def pixelize_image(image: Image.Image, block_size: int = 5) -> Image.Image:
	"""Reduce and enlarge with nearest-neighbor sampling to create square blocks."""
	if block_size < 1:
		raise ValueError("block_size must be positive")
	small_size = (
		max(1, (image.width + block_size - 1) // block_size),
		max(1, (image.height + block_size - 1) // block_size),
	)
	small = image.resize(small_size, Image.Resampling.BOX)
	return small.resize(image.size, Image.Resampling.NEAREST)


def add_noise(image: Image.Image, amount: float, seed: int | None = None) -> Image.Image:
	"""Add reproducible monochrome noise centered around zero to an RGB image."""
	if amount < 0:
		raise ValueError("noise amount cannot be negative")
	if amount == 0:
		return image.copy()
	rng = random.Random(seed)
	noise_values = [
		max(0, min(255, round(rng.gauss(128, amount))))
		for _ in range(image.width * image.height)
	]
	noise = Image.new("L", image.size)
	noise.putdata(noise_values)
	return ImageChops.add(image.convert("RGB"), noise.convert("RGB"), scale=1.0, offset=-128)


def invert_luminosity(image: Image.Image) -> Image.Image:
	"""Convert to grayscale and invert its luminosity curve."""
	return ImageOps.invert(ImageOps.grayscale(image)).convert("RGB")


def _load_font(font_path: str | Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
	try:
		return ImageFont.truetype(str(font_path), size)
	except OSError:
		fallback = Path(__file__).with_name("DejaVuSans-Bold.ttf")
		if fallback.exists():
			return ImageFont.truetype(str(fallback), size)
		return ImageFont.load_default()


def _wrap_caption(draw: ImageDraw.ImageDraw, caption: str, font: ImageFont.ImageFont, max_width: int) -> str:
	words = caption.split()
	lines: list[str] = []
	current = ""
	for word in words:
		candidate = f"{current} {word}".strip()
		if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
			lines.append(current)
			current = word
		else:
			current = candidate
	if current:
		lines.append(current)
	return "\n".join(lines)


def render_caption(
	image: Image.Image,
	caption: str,
	font_path: str | Path = DEFAULT_FONT,
) -> Image.Image:
	"""Draw centered, fitted Impact-style white text with a black outline."""
	if not caption.strip():
		raise ValueError("caption cannot be empty")
	draw = ImageDraw.Draw(image)
	max_width = int(image.width * 0.92)
	max_height = int(image.height * 0.38)
	stroke_width = max(2, image.width // 180)
	font_size = max(20, image.height // 5)
	while font_size >= 20:
		font = _load_font(font_path, font_size)
		wrapped = _wrap_caption(draw, caption, font, max_width)
		bbox = draw.multiline_textbbox(
			(0, 0), wrapped, font=font, stroke_width=stroke_width, spacing=max(2, font_size // 10)
		)
		if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
			break
		font_size -= max(2, image.height // 100)
	else:
		font = _load_font(font_path, 20)
		wrapped = _wrap_caption(draw, caption, font, max_width)
	spacing = max(2, font_size // 10)
	bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, stroke_width=stroke_width, spacing=spacing)
	position = ((image.width - (bbox[2] - bbox[0])) / 2, (image.height - (bbox[3] - bbox[1])) / 2)
	draw.multiline_text(
		position,
		wrapped,
		font=font,
		fill="white",
		stroke_width=stroke_width,
		stroke_fill="black",
		spacing=spacing,
		align="center",
	)
	return image


def generate_epiphany(
	settings_path: str | Path = "settings.yml",
	*,
	seed_words: Sequence[str] | None = None,
	seed: int | None = None,
) -> EpiphanyResult:
	"""Generate a captioned, filtered image and retain attribution metadata."""
	settings = load_generation_settings(settings_path)
	project_root = Path(settings_path).parent
	configure_logging(project_root)
	LOGGER.info("generation started settings=%s seed=%s fully_random=%s", settings_path, seed, settings["fully_random"])
	image_fetcher = fetch_random_image if settings["fully_random"] else fetch_configured_image
	image_result = image_fetcher(settings_path, seed=seed)
	LOGGER.info("image selected title=%r source=%s search=%r", image_result.title, image_result.source_url, image_result.search_term)
	caption = generate_caption(
		project_root / "lexicon" / "vocab.json",
		settings_path,
		seed_words=seed_words,
		seed=seed,
	)
	LOGGER.info("caption generated text=%r", caption)
	with Image.open(io.BytesIO(image_result.data)) as source:
		image = resize_to_resolution(source, settings["width"], settings["height"])
	image = invert_luminosity(image)
	image = render_caption(image, caption, settings["font_path"])
	image = pixelize_image(image, settings["pixel_block_size"])
	image = add_noise(image, settings["noise_amount"], seed=seed)
	LOGGER.info("generation finished size=%sx%s", image.width, image.height)
	return EpiphanyResult(image, caption, image_result.attribution_markdown)


def generate_and_save(
	settings_path: str | Path = "settings.yml",
	*,
	seed_words: Sequence[str] | None = None,
	seed: int | None = None,
) -> Path:
	"""Generate an epiphany and save it to the configured output path."""
	settings = load_generation_settings(settings_path)
	try:
		result = generate_epiphany(settings_path, seed_words=seed_words, seed=seed)
	except Exception:
		configure_logging(Path(settings_path).parent)
		LOGGER.exception("generation failed settings=%s seed=%s", settings_path, seed)
		raise
	output_path = Path(settings["output_path"])
	if not output_path.is_absolute():
		output_path = Path(settings_path).parent / output_path
	result_path = result.save(output_path)
	LOGGER.info("output saved path=%s", result_path)
	return result_path


def _main() -> None:
	parser = argparse.ArgumentParser(description="Generate a filtered, captioned epiphany image.")
	parser.add_argument("settings", nargs="?", default="settings.yml")
	parser.add_argument("--seed", type=int, help="reproduce the same image and caption")
	args = parser.parse_args()
	output_path = generate_and_save(args.settings, seed=args.seed)
	print(f"Generated epiphany: {output_path}")


if __name__ == "__main__":
	_main()
