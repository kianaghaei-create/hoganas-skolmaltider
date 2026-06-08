# Skolmåltidsanalys (PoC)

Detta projekt läser stökiga Excel-filer från skolmåltidsverksamhet och bygger en första normaliserad analysgrund för:
- inköp (`purchases`)
- matsvinn (`food_waste`)
- portioner (`portions`)
- meny/näring (`menu_nutrition`)
- förskoledebitering (`preschool_billing`)

## Struktur

- `data/raw/` rådata (valfritt)
- `data/processed/` exporterade tabeller (Parquet/CSV)
- `reports/` rapporter (Markdown)
- `src/` kodmoduler
- `main.py` kör hela pipelinen

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Körning

```bash
python3 main.py
```

## Output

Efter körning skapas:
- `data/processed/purchases.parquet`
- `data/processed/food_waste.parquet`
- `data/processed/portions.parquet`
- `data/processed/menu_nutrition.parquet`
- `data/processed/preschool_billing.parquet`
- `data/processed/table_summary.csv`
- `reports/data_quality_report.md`
- `reports/analysis_report.md`

## Vad koden gör

1. Hittar `.xlsx`-filer i projektroten och `Data/`.
2. Läser alla blad och försöker hitta rubrikrad automatiskt.
3. Detekterar filkategori med filnamn + blad + kolumnmönster.
4. Standardiserar kolumnnamn och lägger metadata (`source_file`, `source_sheet`, kategori).
5. Exporterar normaliserade tabeller.
6. Kör datakvalitetskontroller och bygger första analysrapport.

## Kända begränsningar (första version)

- Vissa mallblad har rubriker på ovanliga rader och kan kräva finjusterad parser.
- Koppling mellan meny/rätt och svinn kräver fler robusta nycklar (datum/enhet/rätt-id).
- Kostnad per portion är indikativ tills inköp kopplas strikt på enhet/tid/kategori.
