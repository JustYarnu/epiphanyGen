"""Create diagnostic reports for epiphanyGen without generating an image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
	from .caption_generator import load_sentence_templates, load_settings, load_vocabulary
	from .epiphany_generator import load_generation_settings
	from .img_grabber import load_image_settings
	from .list_domains import list_domains, write_options
except ImportError:  # Allows ``python generator/debugger.py``.
	from caption_generator import load_sentence_templates, load_settings, load_vocabulary
	from epiphany_generator import load_generation_settings
	from img_grabber import load_image_settings
	from list_domains import list_domains, write_options


def build_report(project_root: str | Path = ".") -> dict[str, Any]:
	"""Collect configuration, vocabulary, template, and output diagnostics."""
	project_root = Path(project_root)
	settings_path = project_root / "settings.yml"
	vocabulary_path = project_root / "lexicon" / "vocab.json"
	template_path = project_root / "lexicon" / "sentence_templates.json"
	generation_settings = load_generation_settings(settings_path)
	image_settings = load_image_settings(settings_path)
	caption_settings = load_settings(settings_path)
	words = load_vocabulary(vocabulary_path)
	templates = load_sentence_templates(template_path)
	domains = list_domains(vocabulary_path)
	permitted = {domain.lower() for domain in caption_settings["permitted_domains"]}
	matching_words = [word for word in words if word.has_domain(permitted)]

	return {
		"settings_path": str(settings_path),
		"fully_random": generation_settings["fully_random"],
		"permitted_domains": caption_settings["permitted_domains"],
		"available_domains": domains,
		"matching_word_count": len(matching_words),
		"vocabulary_word_count": len(words),
		"template_count": len(templates),
		"image_keywords": image_settings["image_keywords"],
		"output_path": str(generation_settings["output_path"]),
	}


def write_report(project_root: str | Path = ".") -> Path:
	"""Write options.txt and report.json under the project's debug directory."""
	project_root = Path(project_root)
	vocabulary_path = project_root / "lexicon" / "vocab.json"
	debug_dir = project_root / "debug"
	debug_dir.mkdir(parents=True, exist_ok=True)
	write_options(vocabulary_path, debug_dir / "options.txt")
	report_path = debug_dir / "report.json"
	report_path.write_text(
		json.dumps(build_report(project_root), indent=2) + "\n",
		encoding="utf-8",
	)
	return report_path


def main() -> None:
	project_root = Path(__file__).resolve().parents[1]
	parser = argparse.ArgumentParser(description="Write epiphanyGen debug reports.")
	parser.add_argument("--project-root", type=Path, default=project_root)
	args = parser.parse_args()
	print(write_report(args.project_root))


if __name__ == "__main__":
	main()
