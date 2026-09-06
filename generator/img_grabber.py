"""Fetch a keyword-selected image for later filtering and composition."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
DEFAULT_TIMEOUT = 15.0


@dataclass(frozen=True)
class ImageResult:
	"""Downloaded image bytes, provenance, and reusable attribution text."""
	data: bytes
	content_type: str
	source_url: str
	search_term: str
	title: str
	author: str
	license_name: str
	license_url: str
	page_url: str
	attribution_markdown: str

	def save_bundle(self, image_path: str | Path) -> Path:
		"""Save the image and a same-stem Markdown attribution sidecar."""
		image_path = Path(image_path)
		image_path.parent.mkdir(parents=True, exist_ok=True)
		image_path.write_bytes(self.data)
		image_path.with_suffix(".md").write_text(self.attribution_markdown + "\n", encoding="utf-8")
		return image_path


def load_image_settings(path: str | Path) -> dict[str, Any]:
	"""Read image keywords and endpoint from the project's simple YAML settings."""
	keywords: list[str] = []
	endpoint = DEFAULT_ENDPOINT
	fully_random = False
	reading_keywords = False

	for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
		line = raw_line.split("#", 1)[0].strip()
		if not line:
			continue
		if line.startswith("image_keywords"):
			reading_keywords = True
			inline_value = line.partition(":")[2].strip()
			if inline_value.startswith("[") and inline_value.endswith("]"):
				keywords.extend(
					item.strip().strip("'\"")
					for item in inline_value[1:-1].split(",")
					if item.strip()
				)
			continue
		if line.startswith("image_api_endpoint"):
			endpoint = line.partition(":")[2].strip().strip("'\"")
			reading_keywords = False
			continue
		if line.startswith("fully_random"):
			value = line.partition(":")[2].strip().lower()
			if value not in {"true", "false"}:
				raise ValueError("fully_random must be true or false")
			fully_random = value == "true"
			reading_keywords = False
			continue
		if reading_keywords and line.startswith("-"):
			keyword = line[1:].strip().strip("'\"")
			if keyword:
				keywords.append(keyword)
			continue
		if reading_keywords and not raw_line.startswith((" ", "\t")):
			reading_keywords = False

	if not keywords:
		raise ValueError(f"No image_keywords found in {path}")
	if not endpoint:
		raise ValueError("image_api_endpoint cannot be empty")
	return {
		"image_keywords": keywords,
		"image_api_endpoint": endpoint,
		"fully_random": fully_random,
	}


def _metadata_value(metadata: Mapping[str, Any], key: str, fallback: str = "") -> str:
	value = metadata.get(key, {})
	if isinstance(value, dict):
		return str(value.get("value", fallback)).strip() or fallback
	return str(value).strip() or fallback


def _search_image(
	endpoint: str,
	search_term: str,
	timeout: float,
	seed: int | None = None,
) -> dict[str, str]:
	"""Resolve a search term to an image plus its Commons license metadata."""
	query = urlencode(
		{
			"action": "query",
			"generator": "search",
			"gsrsearch": search_term,
			"gsrnamespace": 6,
			"gsrlimit": 10,
			"prop": "imageinfo",
			"iiprop": "url|mime|extmetadata",
			"format": "json",
			"origin": "*",
		}
	)
	request = Request(
		f"{endpoint}?{query}",
		headers={"User-Agent": "epiphanyGen/0.1 (image retrieval)"},
	)
	try:
		with urlopen(request, timeout=timeout) as response:
			payload = json.loads(response.read().decode("utf-8"))
	except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
		raise RuntimeError(f"Image search failed for '{search_term}': {error}") from error

	pages = payload.get("query", {}).get("pages", {})
	candidates: list[dict[str, str]] = []
	for page in pages.values():
		image_info = page.get("imageinfo", [])
		if not image_info or not image_info[0].get("url"):
			continue
		info = image_info[0]
		if info.get("mime") == "image/svg+xml":
			continue
		metadata = info.get("extmetadata", {})
		license_name = _metadata_value(metadata, "LicenseShortName")
		license_url = _metadata_value(metadata, "LicenseUrl")
		if not license_name or not license_url:
			continue
		candidates.append(
			{
				"image_url": info["url"],
				"title": page.get("title", "Untitled Commons image"),
				"author": _metadata_value(metadata, "Artist", "Unknown author"),
				"license_name": license_name,
				"license_url": license_url,
				"page_url": _metadata_value(metadata, "CommonsMetadataExtension", "")
					or f"https://commons.wikimedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
			}
		)
	if candidates:
		return random.Random(seed).choice(candidates)
	raise LookupError(f"No image found for keyword search: {search_term}")


def _download_image(image: Mapping[str, str], search_term: str, timeout: float) -> ImageResult:
	image_url = image["image_url"]
	request = Request(image_url, headers={"User-Agent": "epiphanyGen/0.1 (image retrieval)"})
	try:
		with urlopen(request, timeout=timeout) as response:
			data = response.read()
			content_type = response.headers.get_content_type()
	except (HTTPError, URLError, TimeoutError) as error:
		raise RuntimeError(f"Image download failed for '{search_term}': {error}") from error
	if not data:
		raise RuntimeError(f"Image download returned no data for '{search_term}'")
	if not content_type.startswith("image/"):
		raise RuntimeError(f"Image endpoint returned unexpected content type: {content_type}")
	attribution = (
		f"# {image['title']}\n\n"
		f"![{image['title']}]({image_url})\n\n"
		f"**Artist:** {image['author']}  \n"
		f"**License:** [{image['license_name']}]({image['license_url']})  \n"
		f"**Source:** [{image['title']}]({image['page_url']})  \n"
		f"**Search keywords:** {search_term}\n"
	)
	return ImageResult(
		data=data,
		content_type=content_type,
		source_url=image_url,
		search_term=search_term,
		title=image["title"],
		author=image["author"],
		license_name=image["license_name"],
		license_url=image["license_url"],
		page_url=image["page_url"],
		attribution_markdown=attribution,
	)


def fetch_image(
	keywords: str | list[str],
	*,
	endpoint: str = DEFAULT_ENDPOINT,
	timeout: float = DEFAULT_TIMEOUT,
	seed: int | None = None,
) -> ImageResult:
	"""Search for and download one image using one or more keyword phrases."""
	if timeout <= 0:
		raise ValueError("timeout must be positive")
	if isinstance(keywords, str):
		search_term = keywords.strip()
	else:
		search_term = " ".join(keyword.strip() for keyword in keywords if keyword.strip())
	if not search_term:
		raise ValueError("At least one image keyword is required")

	image = _search_image(endpoint, search_term, timeout, seed=seed)
	return _download_image(image, search_term, timeout)


def fetch_configured_image(settings_path: str | Path, seed: int | None = None) -> ImageResult:
	"""Fetch an image using the keywords and endpoint configured in YAML."""
	settings = load_image_settings(settings_path)
	keywords = settings["image_keywords"]
	return fetch_image(
		" OR ".join(keywords),
		endpoint=settings["image_api_endpoint"],
		seed=seed,
	)


def fetch_random_image(settings_path: str | Path, seed: int | None = None) -> ImageResult:
	"""Fetch an unrestricted random, license-attributed Wikimedia Commons image."""
	settings = load_image_settings(settings_path)
	query = urlencode(
		{
			"action": "query",
			"generator": "random",
			"grnnamespace": 6,
			"grnlimit": 10,
			"prop": "imageinfo",
			"iiprop": "url|mime|extmetadata",
			"format": "json",
			"origin": "*",
		}
	)
	request = Request(
		f"{settings['image_api_endpoint']}?{query}",
		headers={"User-Agent": "epiphanyGen/0.1 (random image retrieval)"},
	)
	try:
		with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
			payload = json.loads(response.read().decode("utf-8"))
	except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
		raise RuntimeError(f"Random image search failed: {error}") from error

	pages = payload.get("query", {}).get("pages", {})
	candidates: list[dict[str, str]] = []
	for page in pages.values():
		image_info = page.get("imageinfo", [])
		if not image_info or not image_info[0].get("url"):
			continue
		info = image_info[0]
		if info.get("mime") == "image/svg+xml":
			continue
		metadata = info.get("extmetadata", {})
		license_name = _metadata_value(metadata, "LicenseShortName")
		license_url = _metadata_value(metadata, "LicenseUrl")
		if not license_name or not license_url:
			continue
		candidates.append(
			{
				"image_url": info["url"],
				"title": page.get("title", "Untitled Commons image"),
				"author": _metadata_value(metadata, "Artist", "Unknown author"),
				"license_name": license_name,
				"license_url": license_url,
				"page_url": _metadata_value(metadata, "CommonsMetadataExtension", "")
					or f"https://commons.wikimedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
			}
		)
	if not candidates:
		raise LookupError("No license-attributed random image found")

	image = random.Random(seed).choice(candidates)
	return _download_image(image, "random Wikimedia Commons", DEFAULT_TIMEOUT)
