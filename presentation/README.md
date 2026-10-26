# Presentation

`earspectro_deck.pptx`: 29-slide overview of the EarSpectro framework (formulas, architecture,
pipeline, datasets, references) and the synthetic-data results as native PowerPoint charts.

Rebuild (needs python-pptx, matplotlib, pandas):

```bash
python presentation/formulas.py presentation/formulas
python presentation/build_deck.py . presentation/formulas presentation/earspectro_deck.pptx
```

`formulas.py` renders every equation to PNG with matplotlib mathtext; `build_deck.py` reads the
result CSVs under `outputs/` so the charts always match the latest run.

`earspectro_short.pptx`: 6-slide overview (title, pipeline, signal model and data, key formulas, two results
slides). Build it by appending `short_slides.py` to the helper section of `build_deck.py` (its first 298 lines):

```bash
head -n 298 presentation/build_deck.py > /tmp/build_short.py && cat presentation/short_slides.py >> /tmp/build_short.py
python /tmp/build_short.py . presentation/formulas presentation/earspectro_short.pptx
```
