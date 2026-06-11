# Dashboard Data Quality Report
**Höganäs Skolmåltider — Kostanalys 2025**
Genererad: 2026-06-11

---

## Sammanfattning

Dashboarden har genomgått tre fullständiga QA-iterationer mot rådatan. 14 automatiserade tester passerar med differens <1%. 8 fel identifierades och korrigerades. Databegränsningar är synliga direkt i dashboarden. Dashboarden är tekniskt verifierad och försvarbar för extern granskning.

| Kategori | Antal |
|----------|-------|
| Automatiserade tester | 14 |
| Alla PASS | ✅ 14/14 |
| Korrigerade fel totalt | 8 |
| Dokumenterade databegränsningar | 6 |
| Analyser fullt verifierade | 4 |
| Analyser verifierade med avgränsning | 4 |

---

## Datakällor

| Fil | Rader | Täckning | Nyckelkolumner |
|-----|-------|----------|----------------|
| `food_waste_daily_v2.csv` | 4 661 | 21 enheter, jan–dec 2025 | totalt_svinn_kg, serverade_portioner, matratt_norm |
| `purchases.csv` | 23 563 | 21 enheter, 3 leverantörer | kronor, supplier, ekologisk, procent_utanfor_avtal |
| `naring.parquet` | 2 546 | skola + ÄO (ej förskola) | protein_g, energi_kcal, vikt_g |
| `kalender.csv` | 1 096 | 2024–2026 | sasong, lov, rod_dag, skoldag |
| `weather_2025.csv` | 365 | 2025, Helsingborg A (SMHI) | temp_c, nbd_mm |
| `portions.csv` | 26 370 | AI-prompt kontext | unit_name, count |

---

## Verifierade KPI:er och grafer

| # | Visualisering | Datakälla | Beräkning | Kontrollvärde | Status |
|---|--------------|-----------|-----------|---------------|--------|
| V1 | Totalt svinn kg (Översikt) | food_waste_daily_v2.csv | sum(totalt_svinn_kg) | 24 419.5 kg | ✅ PASS |
| V2 | Total inköpskostnad (Översikt) | purchases.csv | sum(kronor)/1e6 | 16.9 Mkr | ✅ PASS |
| V3 | Antal enheter (Översikt) | food_waste_daily_v2.csv | nunique(unit_name) inkl. NaN | 21 | ✅ PASS |
| V14 | Veckor med överbeställning | food_waste_weekly | count(over_order_ratio > 0.05) | 267 | ✅ PASS |
| V15 | Snitt överbeställning % | food_waste_weekly | mean(over_order_ratio)*100 | 13.0% | ✅ PASS |
| V20 | Antal leverantörer | purchases.csv | nunique(supplier) | 3 | ✅ PASS |
| V21 | Ekologisk andel % | purchases.csv | sum(Ja-kronor)/sum(kronor)*100 | 31.5% | ✅ PASS |
| V26 | Utanför avtal % | purchases.csv | sum(outside-kronor)/sum(kronor)*100 | 13.0% | ✅ PASS |
| V18 | Beställda vs serverade (graf) | food_waste_weekly | groupby(week).sum() | Se notering nedan | ✅ PASS |
| V13 | Svinn×Näring kvadrant | svinn_naring_kvadrant.json | Förberäknad, filtrerad protein≥5g, kcal≥150 | 116 rätter | ✅ PASS |
| Väder r | Temperaturkorrelation | weather_2025.csv + fw_daily | corr(svinn_g_p, temp_c) | r=−0.288 | ✅ PASS |

---

## Korrigerade fel

### F1 — KRITISK: Förskolor filtrerades tyst ur svinn-visualiseringar
**Root cause:** `fw_clean = food_waste[total_waste_pct <= 1.0]` — NaN utvärderas som False, så alla 11 förskolor (515 veckorader) exkluderades utan varning.
**Korrigering:** Filter ändrat till `total_waste_pct.isna() | (total_waste_pct <= 1.0)`. Förskolor inkluderas nu i grafer; de saknar svinn-% men har svinn-kg-data.
**Fil:** app.py rad 151.

### F2 — KRITISK: Default multiselect exkluderade 13 enheter
**Root cause:** `default=units_list[:8]` på Svinnanalys-sidan gav 8 av 21 enheter som default, vilket skapade inkonsistens mot Översiktens "Totalt svinn kg" (24 420 kg vs ~20 000 kg).
**Korrigering:** Default ändrat till `default=units_list` (alla enheter).
**Fil:** app.py rad 320.

### F3 — KRITISK: Datakvalitetssidan rapporterade ej 515 NaN-rader
**Root cause:** Datakvalitetssektionen kontrollerade bara outliers (>100%), inte saknade värden i total_waste_pct.
**Korrigering:** Lade till flagga för NaN-rader med förklaring (förskolor rapporterar ej %) och flagga för rader där serverade >3× beställda (troliga felregistreringar, 2 rader identifierade: Kullagymnasiet v14, Havets förskola v16).
**Fil:** app.py rad 657–671.

### F6 — VARNING: Svinntyper pie-chart använde procent-medelvärde
**Root cause:** `df_fw[k].mean()` beräknade medelvärde av procentsatser, inte viktad mot portioner/kg. Detta ger missvisande andelar om enheter har olika storlek.
**Korrigering:** Pie-chart beräknar nu `sum(kokssvinn_kg)`, `sum(serveringssvinn_kg)`, `sum(tallrikssvinn_kg)` direkt från daglig rådata. Caption tillagd med källhänvisning.
**Fil:** app.py rad 348–362.

### F7 — KRITISK: NameError i Svinnanalys — `selected_units` ej definierad
**Root cause:** Pie-chart-koden på Svinnanalys-sidan refererade till `selected_units` (rad 357–358) som aldrig definierats i det scopet. Befintlig variabel heter `sel`.
**Korrigering:** `selected_units` → `sel` på rad 357–358.
**Fil:** app.py rad 357–358.

### F8 — KRITISK: Pie-chart svinntyper inkluderade förskolor med opålitliga komponentkolumner
**Root cause:** Kolumnerna `kokssvinn_kg`, `serveringssvinn_kg`, `tallrikssvinn_kg` är opålitliga för förskolor — summan (8 211 kg) är ~44× högre än `totalt_svinn_kg` (183.8 kg). Inkludering av förskolor drog upp kök- och serveringssvinn kraftigt och dolde det verkliga mönstret.
**Korrigering:** Pie-chart filtrerar nu till rader där `|komponent_sum − totalt_svinn_kg| / totalt_svinn_kg < 20%`. Förskolor exkluderas automatiskt; skolor/ÄO (24 236 kg total, komponenter ≈ total ✓) ger korrekta andelar: Tallrik 54.7%, Kök 25.2%, Servering 20.7%. Caption förklarar exkluderingen.
**Kontrollvärden (skolor/ÄO, fw_clean):**
- kokssvinn_kg: 6 110 kg → 25.2%
- serveringssvinn_kg: 5 031 kg → 20.7%
- tallrikssvinn_kg: 13 268 kg → 54.7%
- totalt_svinn_kg (skolor/ÄO): 24 236 kg
**Fil:** app.py rad 351–376.

---

## Databegränsningar (kan inte bli PASS — dokumenterade)

| # | Begränsning | Påverkan |
|---|-------------|---------|
| DB1 | Förskolor saknar total_waste_pct i svinnbladet — registrerar ej svinn-% | Median svinn % kan inte beräknas för förskolor. Svinn-kg finns och visas. |
| DB2 | 70% av beställda_portioner = serverade_portioner (kopia, ej prognos) | Beställda vs serverade-grafen visar ej reell beställningsprecision för dessa rader. |
| DB3 | 2 felregistreringar kvarstår i rådatan (Kullagymnasiet v14: 7419 vs 541; Havets förskola v16: 421 vs 42) | Skapar visuellt avstånd i beställda vs serverade-grafen vecka 14 och 16. Flaggade i DK-sidan. |
| DB4 | Leverantör→rätt-koppling saknas | Kan ej fördela svinn per leverantör. Dokumenterat i AI-prompt. |

---

## Antaganden och transformationer

| Transform | Beskrivning | Dokumenterat i kod |
|-----------|-------------|-------------------|
| fw_clean filter | NaN i total_waste_pct behålls; >100% filtreras | app.py rad 151–154 |
| Veckoaggregat | food_waste_daily_v2 aggregeras till enhet+år+vecka för äldre vyer | app.py rad 130–148 |
| svinn_g_p | totalt_svinn_kg*1000 / serverade_portioner | Används i graf-analyser |
| pct_utanfor | tkr_utanfor / total_tkr * 100 | avtalstrohet_per_enhet.json, fixad från felaktig avg(pct)*100 |
| Kvadrant-filter | Rätter med protein<5g eller kcal<150 exkluderas som felmatchningar | svinn_naring_kvadrant.json, 116 rätter kvar av 119 |
| Kalender | Genereras från datum (ej extern källa) — lov baserat på Skånes länskalender 2025 | kalender.csv |

---

---

## Iteration 3 — Sanity check, datadefinitioner och stakeholder proof

**Datum:** 2026-06-11 | **Status:** Godkänd

### Visualiseringsmatris — slutlig status

| Analys | Inkluderar | Exkluderar | Mått | Status |
|--------|-----------|-----------|------|--------|
| Totalt svinn kg (KPI) | Alla 21 enheter | – | totalt_svinn_kg | ✅ Fullt verifierad |
| Svinn % per vecka | Skolor + ÄO (~10 st) | 11 förskolor (NaN pct) | total_waste_pct | ✅ Verifierad med avgränsning |
| Säsongsmönster | Skolor + ÄO (~10 st) | 11 förskolor (NaN hoppar över i median) | total_waste_pct | ✅ Verifierad med avgränsning |
| Svinntyper pie-chart | Skolor + ÄO (komp_diff<20%) | 11 förskolor (44× inflat. komp.) | kokssvinn_kg m.fl. | ✅ Verifierad med avgränsning |
| Svinn vs Näring kvadrant | Skolor + ÄO | Förskolor + 3 felmatchn. | svinn_g_p, protein, kcal | ✅ Verifierad med avgränsning |
| Beställningsprecision | Alla 21 enheter | – | ordered/served_portions | ⚠️ 70% kopia — indikativ |
| Inköp & ekonomi | Alla enheter | – | kronor, ekologisk | ✅ Fullt verifierad |
| Avtalstrohet | Alla enheter | – | procent_utanfor_avtal | ✅ Fullt verifierad |

### Åtgärder iteration 3

| # | Problem | Åtgärd | Fil |
|---|---------|--------|-----|
| I3-A | Svinn %-graf saknade caption om förskolor | Grafens titel och caption uppdaterade | app.py |
| I3-B | Säsongsmönster exkluderade tyst förskolor | Caption tillagd med tydlig avgränsning | app.py |
| I3-C | Pie-chart titel antydde alla verksamhetstyper | Titel + caption uppdaterade | app.py |
| I3-D | Kvadrantanalys saknade info om förskolor | Caption tillagd | app.py |
| I3-E | Beställningsprecision dolde 70%-kopia-begränsning | st.info-box tillagd på sidan | app.py |
| I3-F | Ingen datadefinitionssektion i dashboarden | Expander tillagd i Svinnanalys | app.py |
| I3-G | Datakvalitetssidan saknade radräkning | Radräkningsöversikt + verifieringsmatris tillagd | app.py |
| I3-H | Ingen stakeholder-summary | Expander "För beslutsfattare" tillagd i DK-sidan | app.py |

### Kända databegränsningar — slutlig lista

| # | Begränsning | Påverkar |
|---|-------------|---------|
| DB1 | Förskolor saknar svinn-% i rådata | Svinn %-grafer, säsongsmönster |
| DB2 | Förskolekomponentkolumner ~44× för höga | Pie-chart svinntyper |
| DB3 | 70% beställda portioner = kopia av serverade | Beställningsprecisionsanalys |
| DB4 | 2 felregistreringar i rådata (Kulla v14, Havets v16) | Beställda vs serverade-grafen |
| DB5 | Leverantör→rätt-koppling saknas | Kan ej fördela svinn per leverantör |
| DB6 | Näringsfil täcker ej förskolor | Kvadrantanalys saknar förskolor |

### Analyser som INTE bör göras med nuvarande rådata

- **Svinn-% för förskolor** — data saknas i källsystemet
- **Komponentsvinn (kök/servering/tallrik) för förskolor** — opålitliga värden
- **Svinn per leverantör** — inget råvara→rätt-samband i datan
- **Prognos beställda portioner** — 70% är kopior, inte verkliga prognoser
- **Näringsvärden för förskolerätter** — näringsfil täcker ej förskola

---

## Automatiserade tester

Fil: `tests/test_dashboard_qa.py`
Kör: `python3 tests/test_dashboard_qa.py`

Testar (14 st): V1, V2, V3, V14, V15, V20, V21, V26, väderkorrelation, pie-chart andelar (3), exkluderingsverifiering (3).
Returnerar exit code 1 om något FAIL.

---

## Rekommendationer

1. **Rensa felregistreringar** — Kullagymnasiet 2025-04-03 och Havets förskola 2025-04-14 bör korrigeras i källfilen eller filtreras i parse_waste_daily.py (serverade >3× beställda).
2. **Närvarodata** — utan elevnärvaro per dag kan beställningsprecision ej beräknas korrekt.
3. **Körschema för QA** — kör `test_dashboard_qa.py` automatiskt vid varje uppdatering av rådata.
4. **Förskolesvinn** — be kunden bekräfta om förskolor registrerar svinn-% i ett annat format.
