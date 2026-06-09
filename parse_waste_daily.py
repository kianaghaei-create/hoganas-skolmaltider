"""
Daglig svinnparsare — baserad på Manus-analys, anpassad för lokal miljö.
Läser strukturen:
  Rad 1: Kökets namn
  Rad 2: Veckonummer + År
  Rad 3: Portionsvikt
  Rad 6: Maträtt per dag (C=Mån, D=Tis, E=Ons, F=Tor, G=Fre)
  Rad 8: Beställda portioner
  Rad 10: Serverade portioner
  Rad 11-13: Köks/serverings/tallrikssvinn (kg)
  Rad 14: Totalt svinn (kg)
  Rad 15-18: Svinntyper (%)
"""
from pathlib import Path
import openpyxl
import pandas as pd
import re
from datetime import datetime, timedelta

WASTE_DIR = Path("Data/Matsvinn 2025")
OUT       = Path("Data/processed")
OUT.mkdir(parents=True, exist_ok=True)

WEEKDAYS = ['Måndag', 'Tisdag', 'Onsdag', 'Torsdag', 'Fredag']
DAY_COLS  = [2, 3, 4, 5, 6]  # C, D, E, F, G (0-baserat)

def to_float(v):
    if v is None: return None
    try: return float(str(v).replace(',', '.').replace('%', '').strip())
    except: return None

def week_to_monday(year, week):
    try:
        return datetime.strptime(f'{int(year)}-W{int(week):02d}-1', '%G-W%V-%u').date()
    except:
        return None

def parse_week_number(val):
    if val is None: return None
    m = re.search(r'(\d+)', str(val))
    return int(m.group(1)) if m else None

def parse_file(fpath):
    enhet_default = fpath.stem
    records = []
    try:
        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
    except Exception as e:
        print(f"  SKIP {enhet_default}: {e}")
        return records

    for shname in wb.sheetnames:
        if shname in ('Sammanställning', 'ESRI_MAPINFO_SHEET'):
            continue
        ws  = wb[shname]
        rows = list(ws.iter_rows(max_row=25, max_col=10, values_only=True))
        if len(rows) < 13:
            continue

        enhet    = str(rows[0][1]).strip() if rows[0][1] else enhet_default
        week_num = parse_week_number(rows[1][1])
        year     = int(rows[1][3]) if rows[1][3] and str(rows[1][3]).isdigit() else 2025
        if week_num is None:
            continue

        monday       = week_to_monday(year, week_num)
        portionsvikt = to_float(rows[2][1])

        matratts         = [str(rows[5][c]).strip()  if rows[5][c]  else '' for c in DAY_COLS]
        kommentarer      = [str(rows[6][c]).strip()  if rows[6][c]  else '' for c in DAY_COLS]
        bestallda        = [to_float(rows[7][c])                             for c in DAY_COLS]
        serverade        = [to_float(rows[9][c])                             for c in DAY_COLS]
        koks_kg          = [to_float(rows[10][c])                            for c in DAY_COLS]
        serv_kg          = [to_float(rows[11][c])                            for c in DAY_COLS]
        tallrik_kg       = [to_float(rows[12][c])                            for c in DAY_COLS]
        total_kg         = [to_float(rows[13][c]) if len(rows) > 13 else None for c in DAY_COLS]
        koks_pct         = [to_float(rows[14][c]) if len(rows) > 14 else None for c in DAY_COLS]
        serv_pct         = [to_float(rows[15][c]) if len(rows) > 15 else None for c in DAY_COLS]
        tallrik_pct      = [to_float(rows[16][c]) if len(rows) > 16 else None for c in DAY_COLS]
        total_pct        = [to_float(rows[17][c]) if len(rows) > 17 else None for c in DAY_COLS]

        for i, weekday in enumerate(WEEKDAYS):
            # Skippa dagar utan någon data alls
            if not matratts[i] and bestallda[i] is None and koks_kg[i] is None:
                continue
            datum = (monday + timedelta(days=i)) if monday else None
            records.append({
                'enhet':               enhet,
                'fil':                 fpath.name,
                'blad':                shname,
                'vecka':               week_num,
                'ar':                  year,
                'datum':               str(datum) if datum else None,
                'veckodag':            weekday,
                'matratt':             matratts[i],
                'kommentar':           kommentarer[i],
                'portionsvikt_g':      portionsvikt,
                'bestallda_portioner': bestallda[i],
                'serverade_portioner': serverade[i],
                'kokssvinn_kg':        koks_kg[i],
                'serveringssvinn_kg':  serv_kg[i],
                'tallrikssvinn_kg':    tallrik_kg[i],
                'totalt_svinn_kg':     total_kg[i],
                'kokssvinn_pct':       koks_pct[i],
                'serveringssvinn_pct': serv_pct[i],
                'tallrikssvinn_pct':   tallrik_pct[i],
                'totalt_svinn_pct':    total_pct[i],
            })

    wb.close()
    return records

# ── Kör på alla svinnfiler ───────────────────────────────────────────────────
all_records = []
files = sorted(WASTE_DIR.glob('*.xlsx'))
print(f"Processar {len(files)} svinnfiler...")
for fpath in files:
    recs = parse_file(fpath)
    print(f"  {fpath.stem}: {len(recs)} dagsrader")
    all_records.extend(recs)

df = pd.DataFrame(all_records)

# ── Rensa uppenbart felaktig data ────────────────────────────────────────────
df = df[df['totalt_svinn_kg'].fillna(0) < 500]   # max 500 kg/dag rimligt
df = df[df['tallrikssvinn_kg'].fillna(0) < 300]

# ── Normalisera rättnamn ─────────────────────────────────────────────────────
df['matratt_norm'] = df['matratt'].str.lower().str.strip()
df.loc[df['matratt_norm'] == 'none', 'matratt_norm'] = None
df.loc[df['matratt_norm'] == '', 'matratt_norm'] = None

# ── Spara ────────────────────────────────────────────────────────────────────
out_path = OUT / 'food_waste_daily_v2.csv'
df.to_csv(out_path, index=False, encoding='utf-8-sig')

# ── Rapport ──────────────────────────────────────────────────────────────────
print(f"\n✅ {len(df)} rader sparade → {out_path}")
print(f"   Enheter:          {df['enhet'].nunique()}")
print(f"   Datum-range:      {df['datum'].min()} → {df['datum'].max()}")
print(f"   Med rättnamn:     {df['matratt_norm'].notna().sum()} ({df['matratt_norm'].notna().mean()*100:.0f}%)")
print(f"   Med tallrikssvinn:{df['tallrikssvinn_kg'].notna().sum()}")
print(f"   Med totalt svinn: {df['totalt_svinn_kg'].notna().sum()}")

print("\n--- Stickprov: 5 rader med rättnamn och svinn ---")
sample = df[df['matratt_norm'].notna() & df['totalt_svinn_kg'].notna()].head(5)
print(sample[['enhet','datum','veckodag','matratt','serverade_portioner','totalt_svinn_kg']].to_string())

# ── Kontroll: rader per enhet ────────────────────────────────────────────────
print("\n--- Rader per enhet ---")
print(df.groupby('enhet').agg(
    dagar=('datum','count'),
    med_ratt=('matratt_norm', lambda x: x.notna().sum()),
    totalt_svinn_kg=('totalt_svinn_kg','sum')
).round(1).sort_values('dagar', ascending=False).to_string())
