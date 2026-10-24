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
