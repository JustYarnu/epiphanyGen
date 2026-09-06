"""Build a thematically coherent pool of words for caption generation.

This module stops before sentence construction. It selects the permitted
vocabulary, finds nearby words in feature space, and ranks word pairs by how
well their domains, parts of speech, and feature vectors work together.
"""

from __future__ import annotations

import json
import math
import random
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
	from .word import Word
except ImportError:  # Allows ``python generator/caption_generator.py``.
	from word import Word


VECTOR_KEYS = (
	"abstraction",
	"complexity",
	"ideology",
	"philosophy",
	"formality",
	"sentiment",
)


ALLOCATION_TYPES = {"uniform", "increasing", "decreasing", "contrast"}
DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "lexicon" / "sentence_templates.json"


def load_settings(path: str | Path) -> dict[str, Any]:
	"""Load domain and abstraction settings from the project's small YAML file."""
	permitted_domains: list[str] = []
	settings: dict[str, Any] = {}
	fully_random = False
	reading_domains = False

	for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
		line = raw_line.split("#", 1)[0].strip()
		if not line:
			continue
		if line.startswith("abstraction_budget"):
			value = line.partition(":")[2].strip()
			settings["abstraction_budget"] = float(value)
			reading_domains = False
			continue
		if line.startswith("abstraction_allocation"):
			settings["abstraction_allocation"] = line.partition(":")[2].strip().strip("'\"").lower()
			reading_domains = False
			continue
		if line.startswith("fully_random"):
			value = line.partition(":")[2].strip().lower()
			if value not in {"true", "false"}:
				raise ValueError("fully_random must be true or false")
			fully_random = value == "true"
			reading_domains = False
			continue
		if line.startswith("permitted_domains"):
			reading_domains = True
			inline_value = line.partition(":")[2].strip()
			if inline_value.startswith("[") and inline_value.endswith("]"):
				permitted_domains.extend(
					item.strip().strip("'\"")
					for item in inline_value[1:-1].split(",")
					if item.strip()
				)
			continue
		if reading_domains and line.startswith("-"):
			domain = line[1:].strip().strip("'\"")
			if domain:
				permitted_domains.append(domain)
			continue
		if reading_domains and not raw_line.startswith((" ", "\t")):
			reading_domains = False

	if not permitted_domains and not fully_random:
		raise ValueError(f"No permitted_domains found in {path}")
	budget = settings.get("abstraction_budget", 0.65)
	allocation = settings.get("abstraction_allocation", "uniform")
	if not 0.0 <= budget <= 1.0:
		raise ValueError("abstraction_budget must be between 0 and 1")
	if allocation not in ALLOCATION_TYPES:
		raise ValueError(f"abstraction_allocation must be one of {sorted(ALLOCATION_TYPES)}")
	return {
		"permitted_domains": permitted_domains,
		"abstraction_budget": budget,
		"abstraction_allocation": allocation,
		"fully_random": fully_random,
	}


def load_vocabulary(path: str | Path) -> list[Word]:
	"""Load JSON vocabulary records as :class:`Word` objects."""
	records = json.loads(Path(path).read_text(encoding="utf-8"))
	if not isinstance(records, list):
		raise ValueError("Vocabulary must contain a JSON list")

	words: list[Word] = []
	for record in records:
		missing = {key for key in ("text", "pos", "domain", *VECTOR_KEYS) if key not in record}
		if missing:
			raise ValueError(f"Vocabulary entry is missing: {', '.join(sorted(missing))}")
		words.append(
			Word(
				text=record["text"],
				pos=record["pos"],
				domain=record["domain"],
				**{key: record[key] for key in VECTOR_KEYS},
			)
		)
	return words


def select_permitted_words(words: Iterable[Word], permitted_domains: Iterable[str]) -> list[Word]:
	"""Keep words sharing at least one configured domain, preserving source order."""
	permitted = {domain.strip().lower() for domain in permitted_domains if domain.strip()}
	return [word for word in words if word.has_domain(permitted)]


def cosine_similarity(left: Word, right: Word) -> float:
	"""Return cosine similarity for the words' six-dimensional feature vectors."""
	numerator = sum(a * b for a, b in zip(left.vector, right.vector))
	left_length = math.sqrt(sum(value * value for value in left.vector))
	right_length = math.sqrt(sum(value * value for value in right.vector))
	if left_length == 0 or right_length == 0:
		return 0.0
	return max(-1.0, min(1.0, numerator / (left_length * right_length)))


def domain_affinity(left: Word, right: Word) -> float:
	"""Return Jaccard overlap of the two words' domains in the range [0, 1]."""
	union = left.domains | right.domains
	if not union:
		return 0.0
	return len(left.domains & right.domains) / len(union)


def pos_affinity(left: Word, right: Word) -> float:
	"""Score useful grammatical pairings without attempting sentence parsing."""
	if left.pos == right.pos:
		return 0.45 if left.pos in {"noun", "verb"} else 0.30
	if {left.pos, right.pos} == {"noun", "adjective"}:
		return 1.0
	if {left.pos, right.pos} == {"verb", "adverb"}:
		return 0.85
	if {left.pos, right.pos} == {"noun", "verb"}:
		return 0.65
	return 0.35


def word_affinity(left: Word, right: Word) -> float:
	"""Rank how naturally two words belong in one caption theme.

	Cosine similarity carries most of the score; domain and POS affinity keep
	equally-shaped but unrelated words from outranking meaningful pairings.
	"""
	vector_score = max(0.0, cosine_similarity(left, right))
	return (
		0.55 * vector_score
		+ 0.30 * domain_affinity(left, right)
		+ 0.15 * pos_affinity(left, right)
	)


def find_similar_words(
	target: Word,
	candidates: Iterable[Word],
	limit: int = 10,
) -> list[tuple[Word, float]]:
	"""Return the strongest affinity matches for ``target``."""
	if limit < 0:
		raise ValueError("limit must be non-negative")
	ranked = (
		(candidate, word_affinity(target, candidate))
		for candidate in candidates
		if candidate is not target
	)
	return sorted(ranked, key=lambda item: (-item[1], item[0].text, item[0].pos))[:limit]


def abstraction_targets(size: int, budget: float, allocation: str) -> list[float]:
	"""Create target abstraction levels whose mean is approximately ``budget``."""
	if size < 1:
		raise ValueError("size must be positive")
	if not 0.0 <= budget <= 1.0:
		raise ValueError("budget must be between 0 and 1")
	if allocation not in ALLOCATION_TYPES:
		raise ValueError(f"allocation must be one of {sorted(ALLOCATION_TYPES)}")
	if allocation == "uniform":
		return [budget] * size

	low = max(0.0, 2 * budget - 1)
	high = min(1.0, 2 * budget)
	if size == 1:
		return [budget]
	gradient = [low + (high - low) * index / (size - 1) for index in range(size)]
	if allocation == "decreasing":
		gradient.reverse()
	if allocation == "contrast":
		gradient = [high if index % 2 else low for index in range(size)]
	return gradient


def _pool_affinity(word: Word, seeds: Sequence[Word]) -> float:
	return max((word_affinity(seed, word) for seed in seeds), default=0.0)


def build_word_pool(
	vocabulary_path: str | Path,
	settings_path: str | Path,
	*,
	seed_words: Sequence[str] | None = None,
	pool_size: int = 24,
	neighbors_per_seed: int = 6,
) -> list[Word]:
	"""Build a deterministic pool from permitted seeds and their best neighbors.

	With no explicit seeds, the most cross-domain permitted words are used as
	anchors. Explicit seeds must be present in the permitted vocabulary.
	"""
	if pool_size < 1:
		raise ValueError("pool_size must be positive")
	if neighbors_per_seed < 0:
		raise ValueError("neighbors_per_seed must be non-negative")

	settings = load_settings(settings_path)
	words = select_permitted_words(
		load_vocabulary(vocabulary_path),
		settings["permitted_domains"],
	)
	if not words:
		raise ValueError("No vocabulary entries match the permitted domains")

	by_text = {word.text: word for word in words}
	if seed_words:
		seeds = []
		for text in seed_words:
			if text not in by_text:
				raise ValueError(f"Seed word is not permitted or does not exist: {text}")
			seeds.append(by_text[text])
	else:
		seeds = sorted(words, key=lambda word: (-len(word.domains), -word.components["philosophy"], word.text))[:3]

	selected: dict[tuple[str, str], Word] = {}
	for seed in seeds:
		selected[(seed.text, seed.pos)] = seed
		for neighbor, _score in find_similar_words(seed, words, neighbors_per_seed):
			selected[(neighbor.text, neighbor.pos)] = neighbor

	available = words if settings["abstraction_allocation"] == "contrast" else list(selected.values())
	targets = abstraction_targets(
		pool_size,
		settings["abstraction_budget"],
		settings["abstraction_allocation"],
	)
	pool: list[Word] = []
	for seed in seeds:
		if seed not in pool:
			pool.append(seed)
	for target in targets:
		if len(pool) >= pool_size:
			break
		candidates = [word for word in available if word not in pool]
		if not candidates:
			break
		if settings["abstraction_allocation"] == "contrast":
			best = min(
				candidates,
				key=lambda word: (
					abs(word.components["abstraction"] - target),
					_pool_affinity(word, seeds),
					-word.components["philosophy"],
					word.text,
					word.pos,
				),
			)
		else:
			best = max(
				candidates,
				key=lambda word: (
					-abs(word.components["abstraction"] - target),
					_pool_affinity(word, seeds),
					len(word.domains),
					word.text,
					word.pos,
				),
			)
		pool.append(best)

	return pool[:pool_size]


def describe_pool(pool: Sequence[Word]) -> list[Mapping[str, object]]:
	"""Return serializable pool entries for debugging or a future generator UI."""
	return [
		{
			"text": word.text,
			"pos": word.pos,
			"domain": sorted(word.domains),
			"components": dict(word.components),
		}
		for word in pool
	]


def load_sentence_templates(path: str | Path = DEFAULT_TEMPLATE_PATH) -> list[dict[str, Any]]:
	"""Load and validate data-driven sentence templates from JSON."""
	records = json.loads(Path(path).read_text(encoding="utf-8"))
	if not isinstance(records, list) or not records:
		raise ValueError("Sentence templates must contain a non-empty JSON list")

	templates: list[dict[str, Any]] = []
	for record in records:
		if not isinstance(record, dict):
			raise ValueError("Each sentence template must be a JSON object")
		missing = {key for key in ("name", "slots", "tokens") if key not in record}
		if missing:
			raise ValueError(f"Sentence template is missing: {', '.join(sorted(missing))}")
		if not isinstance(record["slots"], list) or not record["slots"]:
			raise ValueError(f"Template {record['name']} must define slots")
		if not isinstance(record["tokens"], list):
			raise ValueError(f"Template {record['name']} tokens must be a list")
		for slot in record["slots"]:
			if not isinstance(slot, dict) or not slot.get("name") or not slot.get("pos"):
				raise ValueError(f"Template {record['name']} has an invalid slot")
		templates.append(record)
	return templates


def _third_person_singular(verb: str) -> str:
	"""Apply the small set of inflections needed by the initial templates."""
	if verb in {"be", "am", "are"}:
		return "is"
	if verb == "have":
		return "has"
	if verb == "do":
		return "does"
	if verb == "go":
		return "goes"
	if verb.endswith(("s", "x", "z", "ch", "sh")):
		return f"{verb}es"
	if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
		return f"{verb[:-1]}ies"
	return f"{verb}s"


def _render_template(template: Mapping[str, Any], words: Sequence[Word]) -> str:
	"""Render a JSON template using named slots and supported inflections."""
	slots = template["slots"]
	if len(slots) != len(words):
		raise ValueError(f"Template {template['name']} received the wrong number of words")
	values = {slot["name"]: word.text for slot, word in zip(slots, words)}
	for slot in slots:
		if slot["pos"] == "verb":
			values[f"{slot['name']}_3sg"] = _third_person_singular(values[slot["name"]])
	try:
		return "".join(token.format(**values) for token in template["tokens"])
	except KeyError as error:
		raise ValueError(f"Template {template['name']} references an unknown value: {error.args[0]}") from error


def _sentence_score(words: Sequence[Word], budget: float, allocation: str) -> float:
	"""Score a filled template for affinity and its intended abstraction shape."""
	if len(words) > 1:
		affinities = [word_affinity(left, right) for left, right in zip(words, words[1:])]
		affinity_score = sum(affinities) / len(affinities)
		if allocation == "contrast":
			affinity_score = 1.0 - affinity_score
	else:
		affinity_score = 0.0
	targets = abstraction_targets(len(words), budget, allocation)
	abstraction_score = 1.0 - sum(
		abs(word.components["abstraction"] - target) for word, target in zip(words, targets)
	) / len(words)
	return 0.65 * affinity_score + 0.35 * abstraction_score


def generate_caption_from_pool(
	pool: Sequence[Word],
	*,
	budget: float = 0.65,
	allocation: str = "uniform",
	templates: Sequence[Mapping[str, Any]] | None = None,
	seed: int | None = None,
) -> str:
	"""Generate a strong, optionally seeded grammatical caption from a pool."""
	if not pool:
		raise ValueError("Cannot generate a caption from an empty pool")
	if not 0.0 <= budget <= 1.0:
		raise ValueError("budget must be between 0 and 1")
	if allocation not in ALLOCATION_TYPES:
		raise ValueError(f"allocation must be one of {sorted(ALLOCATION_TYPES)}")

	candidates: list[tuple[float, str, str]] = []
	for template in templates or load_sentence_templates():
		template_name = template["name"]
		required_pos = tuple(slot["pos"] for slot in template["slots"])
		word_candidates = [
			[word for word in pool if word.pos == part_of_speech]
			for part_of_speech in required_pos
		]
		if any(not options for options in word_candidates):
			continue
		for words in product(*word_candidates):
			if len({id(word) for word in words}) != len(words):
				continue
			template_bonus = float(template.get("bonus", 0.0))
			score = _sentence_score(words, budget, allocation) + template_bonus
			sentence = _render_template(template, words)
			candidates.append((score, template_name, sentence))

	if not candidates:
		raise ValueError("Pool does not contain the parts of speech needed for a sentence")

	ordered = sorted(candidates, key=lambda candidate: (-candidate[0], candidate[1], candidate[2]))
	return random.Random(seed).choice(ordered[: min(5, len(ordered))])[2]


def generate_caption(
	vocabulary_path: str | Path,
	settings_path: str | Path,
	*,
	seed_words: Sequence[str] | None = None,
	pool_size: int = 24,
	neighbors_per_seed: int = 6,
	template_path: str | Path = DEFAULT_TEMPLATE_PATH,
	seed: int | None = None,
) -> str:
	"""Build a configured word pool and generate one optionally seeded caption."""
	settings = load_settings(settings_path)
	if settings["fully_random"]:
		rng = random.Random(seed)
		words = load_vocabulary(vocabulary_path)
		templates = load_sentence_templates(template_path)
		rng.shuffle(templates)
		for template in templates:
			chosen: list[Word] = []
			for slot in template["slots"]:
				options = [
					word for word in words if word.pos == slot["pos"] and word not in chosen
				]
				if not options:
					break
				chosen.append(rng.choice(options))
			else:
				return _render_template(template, chosen)
		raise ValueError("Vocabulary does not contain the parts of speech needed for a sentence")

	pool = build_word_pool(
		vocabulary_path,
		settings_path,
		seed_words=seed_words,
		pool_size=pool_size,
		neighbors_per_seed=neighbors_per_seed,
	)
	return generate_caption_from_pool(
		pool,
		budget=settings["abstraction_budget"],
		allocation=settings["abstraction_allocation"],
		templates=load_sentence_templates(template_path),
		seed=seed,
	)

