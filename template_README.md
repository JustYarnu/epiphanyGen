# Daily epiphany
[IMAGE_HERE]

# epiphanyGen

`epiphanyGen` generates surreal, captioned images by combining a Wikimedia Commons image with a vocabulary-driven sentence generator:

1. An image is selected from Wikimedia Commons.
2. A caption is generated from the project vocabulary and sentence templates.
3. The image is resized, inverted, captioned, pixelated, and textured with noise.
4. The final image and source attribution are saved together.

## Features

- Wikimedia Commons image retrieval with license metadata.
- Keyword-based image selection or unrestricted random image selection.
- Vocabulary filtering by domain.
- Abstraction-aware caption scoring.
- Similarity contrast mode for more unexpected, philosophical pairings.
- Data-driven sentence templates.
- Reproducible output with an optional seed.
- Attribution Markdown sidecars for generated images.
- Separate diagnostic reports and runtime logs.

## Requirements

- Windows 
- Python 3.10 or newer
- Internet access (for Wikimedia Commons image retrieval)
- Pillow 10 or newer

## Installation

Create and activate a virtual environment from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
## Generate an Image

From the project root:

```powershell
python generator/epiphany_generator.py
```

The configured output is written to:

```text
output/epiphany.png
output/epiphany.md
```

The Markdown file contains the Wikimedia image title, source URL, artist, license, and search context.

## Daily README Update

Generate a fresh epiphany and publish it at the top of `README.md` using the template in `template_README.md`:

```powershell
python generator/daily_epiphany.py
```

For a reproducible update, provide a seed:

```powershell
python generator/daily_epiphany.py --seed 42
```

The script updates `output/epiphany.png`, preserves its attribution sidecar, and replaces `[IMAGE_HERE]` in the template with the generated image link.

## Reproducible Generation

Normal runs are intentionally variable. They can select a different source image, caption, and noise pattern.

Pass a seed when an exact result should be reproducible:

```powershell
python generator/epiphany_generator.py --seed 42
```

The seed controls image selection, caption selection, and generated noise. Re-running with the same settings and seed produces the same result when the remote image remains available.

## Configuration

All primary configuration lives in [settings.yml](settings.yml).

### Caption settings

```yaml
permitted_domains:
  - ethical
  - political
  - social
  - philosophical
abstraction_budget: 0.65
abstraction_allocation: contrast
```

`permitted_domains` limits the vocabulary used for normal caption generation. A word is eligible when it contains at least one configured domain.

`abstraction_budget` ranges from `0.0` to `1.0` and controls the target abstraction level.

`abstraction_allocation` accepts:

- `uniform`: keep all word targets near the configured budget.
- `increasing`: move from lower to higher abstraction.
- `decreasing`: move from higher to lower abstraction.
- `contrast`: alternate abstraction levels and reward lower word similarity.

### Image settings

```yaml
image_keywords:
  - old
  - space
  - abstract
image_api_endpoint: https://commons.wikimedia.org/w/api.php
```

Configured keywords are searched as alternatives, allowing the generator to choose from a wider set of valid Commons results.

### Fully random mode

```yaml
fully_random: true
```

When enabled:

- `image_keywords` are ignored.
- A random license-attributed Wikimedia Commons image is selected.
- The entire vocabulary is eligible for caption generation.
- Template and word selection are randomized.

Set it to `false` to use domain and image-keyword filtering.

### Visual settings

```yaml
output_resolution:
  width: 1080
  height: 1080
font_path: C:\Windows\Fonts\impact.ttf
pixel_block_size: 5
noise_amount: 18
output_path: output\epiphany.png
```

The base image is resized and luminosity-inverted first. The caption is then added in white with a black outline. Pixelation and noise are applied afterward to both image and caption.

## Vocabulary and Templates

Vocabulary records live in [lexicon/vocab.json](lexicon/vocab.json). Each record contains:

- `text`
- `pos`
- `domain`
- Six scoring dimensions: `abstraction`, `complexity`, `ideology`, `philosophy`, `formality`, and `sentiment`

Sentence templates live in [lexicon/sentence_templates.json](lexicon/sentence_templates.json). A template defines a name, typed slots, token text, and an optional score bonus.

Example:

```json
{
  "name": "subject_is_adjective",
  "slots": [
    {"name": "subject", "pos": "noun"},
    {"name": "adjective", "pos": "adjective"}
  ],
  "tokens": ["The ", "{subject}", " is ", "{adjective}", "."],
  "bonus": 0.0
}
```

Supported verb placeholders include `{verb_3sg}`. The renderer applies simple English third-person singular inflection for verbs.

## Debugging and Logs

Generate the diagnostic artifacts with:

```powershell
python generator/debugger.py
```

This updates the `debug/` directory:

- `options.txt`: all unique vocabulary domains.
- `report.json`: settings, vocabulary counts, matching-word count, template count, and output configuration.
- `generator.log`: append-only generation events and failure tracebacks.

The log records the selected image, source URL, caption, seed, generation mode, output size, and saved path.

## Project Layout

```text
epiphanyGen/
├── generator/
│   ├── caption_generator.py
│   ├── debugger.py
│   ├── epiphany_generator.py
│   ├── img_grabber.py
│   ├── list_domains.py
│   └── word.py
├── lexicon/
│   ├── sentence_templates.json
│   └── vocab.json
├── debug/
├── output/
├── requirements.txt
├── settings.yml
└── README.md
```
## License and Attribution

The generator preserves attribution metadata returned by Wikimedia Commons in a Markdown sidecar next to each output image. Review the generated sidecar before publishing or redistributing an image, and follow the specific license terms for the selected source.
