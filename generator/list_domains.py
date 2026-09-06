"""Write the vocabulary's available domains to a debug options file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def list_domains(vocabulary_path: str | Path) -> list[str]:
	"""Return sorted, unique domain names from a vocabulary JSON file."""
	records = json.loads(Path(vocabulary_path).read_text(encoding="utf-8"))
	if not isinstance(records, list):
		raise ValueError("Vocabulary must contain a JSON list")

	domains: set[str] = set()
	for record in records:
		for domain in record.get("domain", []):
			if isinstance(domain, str) and domain.strip():
				domains.add(domain.strip())
	return sorted(domains)


def write_options(vocabulary_path: str | Path, output_path: str | Path) -> Path:
	"""Write the available domains to a plain-text options file."""
	output_path = Path(output_path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	lines = ["Available vocabulary domains:", ""]
	lines.extend(f"- {domain}" for domain in list_domains(vocabulary_path))
	output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
	return output_path


def main() -> None:
	project_root = Path(__file__).resolve().parents[1]
	parser = argparse.ArgumentParser(description="List vocabulary domains for settings configuration.")
	parser.add_argument(
		"vocabulary",
		type=Path,
		default=project_root / "lexicon" / "vocab.json",
		nargs="?",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=project_root / "debug" / "options.txt",
	)
	args = parser.parse_args()
	print(write_options(args.vocabulary, args.output))


if __name__ == "__main__":
	main()
