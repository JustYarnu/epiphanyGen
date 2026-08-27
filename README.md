# epiphanyGen

`epiphanyGen` is an algorithmic engine designed to synthesize procedurally generated, pseudo-philosophical prose and superimpose it onto algorithmically degraded imagery. Rather than relying on stochastic sentence assembly, the engine leverages linear algebra and custom abstraction point-allocation models to maintain an uncanny illusion of structural coherence.

---

## Project Architecture

```text
epiphanyGen/
├── lexicon/
│   ├── words.json                          # Core vocabulary
│   ├── semantic_weights.yml                # Tuning variables dictating thematic distribution
│   ├── rhetorical_structure_templates.json # Grammatical blueprints for sentence syntax
│   └── figures_of_speech_templates.json    # Frameworks for procedural rhetoric
└── generator/
    ├── settings.yml                        # Global execution parameters
    ├── generator.py                        # Core pipeline engine
    └── output/                             # Destination for generated artifacts and debug logs
```

---

## Algorithmic Mechanics

Generating random word vomit is easy; generating prose that projects an illusion of profound academia is difficult.

### 1. Semantic Vectorization & Relationship Modeling
Each vocabulary token in `words.json` is mapped via a `semantics` vector. When filling a template placeholder:
* The engine runs a **Cosine Similarity** check against the target semantic profile to form a candidate pool of viable words.
* It evaluates relational strength across candidates using a **Weighted Sum Model** to ensure selected terms share cohesive conceptual vectors with previously chosen tokens.

### 2. Abstraction Point-Allocation Spread
To prevent sentences from collapsing into either literalism or unreadable jargon, the engine enforces an **Abstraction Budget**:
* An abstraction "point pool" is assigned to the sentence scaled directly to its total token length.
* Word abstraction ratings are normalized so their summation equals the maximum allocated points.
* The shape of this abstraction distribution across the sentence is governed by parameters set in `settings.yml`.

### 3. Multi-Candidate Batch Evaluation
If `Batch size` is set above `1`, the generator synthesizes parallel candidate texts in memory, cross-comparing internal relational scores before selecting the mathematically optimal text to render.

---

## Image Retrieval & Processing Pipeline

The image is retrieved using the keywords specified in `settings.yml`. Once acquired, the image undergoes a "destructive" image-editing pipeline via OpenCV and Pillow:

1. **Crop to Fill:** Resizes and crops the source image to match the target canvas aspect ratio.
2. **Pixelation:** Downsamples spatial resolution to remove fine visual detail.
3. **Grayscale Conversion:** Strips color channels to establish a monochrome palette.
4. **Luminosity Inversion:** Inverts tonal values to yield stark visual artifacts.

---

## Configuration (`generator/settings.yml`)

Engine behavior is managed via `settings.yml` (case-insensitive):

* **`Semantic weights`**: Specifies how semantic weights are distributed across vector space.
  * Options: `Random`, `Left-skewed`, `Right-skewed`, `Even`, `Symmetrical`
* **`Image keyword(s)`**: Comma-separated terms used for querying background imagery (e.g., `brutalism,fog,industrial`).
* **`Batch size`**: Number of parallel candidates evaluated per generation cycle.
* **`Candidate pool`**: Number of candidates within a given pool. 
* **`Image width` / `Image height`**: Spatial dimensions of the output image in pixels.

---

## Installation & Execution

### Prerequisites
* Python 3.10+
* Required libraries: `Pillow`, `opencv-python`, `numpy`, `PyYAML`

### Direct Execution
```bash
# Clone repository
git clone [https://github.com/JustYarnu/epiphanyGen.git](https://github.com/JustYarnu/epiphanyGen.git)
cd epiphanyGen

# Install required dependencies
pip install pillow opencv-python numpy pyyaml

# Run the generator
python generator/generator.py
```

Containerization may follow, idk though.