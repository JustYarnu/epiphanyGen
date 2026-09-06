"""Generate the daily epiphany and publish it at the top of README.md."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
	from .epiphany_generator import generate_and_save
except ImportError:  # Allows ``python generator/daily_epiphany.py``.
	from epiphany_generator import generate_and_save


IMAGE_MARKER = "[IMAGE_HERE]"
DEFAULT_TEMPLATE = "template_README.md"
DEFAULT_README = "README.md"


def update_readme(
	project_root: str | Path = ".",
	*,
	settings_path: str | Path = "settings.yml",
	template_path: str | Path = DEFAULT_TEMPLATE,
	readme_path: str | Path = DEFAULT_README,
	seed: int | None = None,
) -> Path:
	"""Generate the image and write a README based on the template marker."""
	project_root = Path(project_root).resolve()
	settings_path = project_root / settings_path
	template_path = project_root / template_path
	readme_path = project_root / readme_path

	output_path = generate_and_save(settings_path, seed=seed)
	output_path = Path(output_path).resolve()
	image_link = str(Path(output_path).relative_to(readme_path.parent)).replace("\\", "/")

	template = template_path.read_text(encoding="utf-8")
	if IMAGE_MARKER not in template:
		raise ValueError(f"README template must contain {IMAGE_MARKER!r}")
	readme = template.replace(IMAGE_MARKER, f"![Daily epiphany]({image_link})", 1)
	readme_path.write_text(readme, encoding="utf-8")
	return readme_path


def main() -> None:
	project_root = Path(__file__).resolve().parents[1]
	parser = argparse.ArgumentParser(description="Generate and publish the daily epiphany in README.md.")
	parser.add_argument("--settings", type=Path, default=Path("settings.yml"))
	parser.add_argument("--template", type=Path, default=Path(DEFAULT_TEMPLATE))
	parser.add_argument("--readme", type=Path, default=Path(DEFAULT_README))
	parser.add_argument("--seed", type=int, help="reproduce the same daily image and caption")
	args = parser.parse_args()
	readme_path = update_readme(
		project_root,
		settings_path=args.settings,
		template_path=args.template,
		readme_path=args.readme,
		seed=args.seed,
	)
	print(f"Updated README: {readme_path}")


if __name__ == "__main__":
	main()
