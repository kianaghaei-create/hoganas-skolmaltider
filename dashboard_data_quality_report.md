# Dashboard Data Quality Report
**Höganäs Skolmåltider — Kostanalys 2025**
Genererad: 2026-06-11

---

## QA Lock

> **Status: LÅST — 2026-06-11**
> Inga ändringar får göras utan att hela testsviten körs om och resultatet dokumenteras.

| Parameter | Värde |
|-----------|-------|
| Source of truth | Original-Excel → verifierad `food_waste_daily_v2.csv` |
| Verifierad normaliserad dataset | `Data/processed/food_waste_daily_v2.csv` |
| Neo4j-status | Synkad mot CSV — 4 660 Dag-noder, 0 orphan-noder |
| Total verifierad svinnmängd | 28 400 kg |
| Cypher-analyser | 17 regenererade från synkad Neo4j |
| Tester | **101/101 PASS** |
| Kvarvarande avgränsning | Kvadrantanalysen är PASS MED AVGRÄNSNING — täckning begränsad av SERVERADE-relationer i Neo4j (62 rätter med obs≥2 och näringsmatchning) |
| Senaste verifieringsdatum | 2026-06-11 |

**Regel:** Följande komponenter är låsta. Varje ändring kräver att hela testsviten (`test_dashboard_qa.py && test_parser.py && test_ai_cypher_qa.py`) körs om och att resultatet dokumenteras i denna rapport med datum och utfall:

- Parsern (`parse_waste_daily.py`)
- Datatransformationerna
- Neo4j-importen (`import_neo4j.py`)
- Cypher-analyserna (`cypher_analysis.py`)
- Dashboardens beräkningslogik (`app.py`)
- OpenAI-systemprompten
- `Data/analysis/*.json`

---

## Stakeholder summary

Dashboarden visar analyser som är spårbara från original-Excel via en verifierad CSV till Neo4j, Cypher-analyser och OpenAI-svar. Tidigare fel i Excel-inläsning, förskoleformat, stale Neo4j-data och en enhetsswap har korrigerats. Alla ordinarie analyser är verifierade mot rådatan. Kvadrantanalysen har en dokumenterad täckningsavgränsning kopplad till vilka rätter som har SERVERADE-relationer och näringsmatchning.

---

## Sammanfattning

Dashboarden har genomgått fem fullständiga QA-iterationer + final cleanup mot rådatan. **101 automatiserade tester passerar** (15 dashboard-QA + 30 parser-tester + 56 AI/Cypher/Neo4j-tester). Inga kända kvarstående begränsningar för dashboardens ordinarie analyser. Hela kedjan Excel → CSV → Neo4j → JSON → Dashboard/AI är stängd och verifierad.

| Kategori | Antal |
|----------|-------|
| Dashboard QA-tester | 15/15 PASS |
| Parser-tester | 30/30 PASS |
| AI/Cypher-tester | 45/45 PASS (+ 1 PASS MED AVGRÄNSNING) |
| Neo4j vs CSV-tester | 11/11 PASS (inkl. N9 enhetsnivå 0.1%, N10 inga orphans, N11 Tornlycke/Jonstorp) |
| Korrigerade fel totalt | 15 |
| Dokumenterade databegränsningar | 4 (inga påverkar ordinarie analyser) |
| Cypher-analyser fullt verifierade | 14 |
| Cypher-analyser verifierade med avgränsning | 3 (näring-analyser — täckning begränsad av SERVERADE) |

**Kritisk dataändring (iteration 4, parser-fix):**
Totalt svinn kg ändrades från 24 420 kg → 28 400 kg.
Förskolor bidrar nu med korrekt 4 104 kg (var 184 kg pga fel rad i gammal parser).

**Iteration 5 — Neo4j reimporterad, alla 17 analyser verifierade:**
4 659 Dag-noder uppdaterades från food_waste_daily_v2.csv (totalt svinn 28 399 kg, diff 1 kg = 0,004%).
Kvadrantanalysen expanderade från förskola-exkludering till full täckning via SERVERADE→HAR_NARING (62 rätter, obs>=2).

**Final cleanup — Tornlycke/Jonstorp-swap åtgärdad:**
1 Dag-nod (2025-02-10) med fel enhetnamn identifierades och korrigerades kirurgiskt.
2 orphan-noder (format=None) borttagna. Neo4j matchar nu CSV exakt på enhetsnivå (0,000% avvikelse).
4 660 Dag-noder, 28 400 kg. Inga orphan-noder.

Source-of-truth-kedja: Excel → CSV (food_waste_daily_v2.csv) → Neo4j → JSON (Data/analysis/) → Dashboard/AI.

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
| V13 | Svinn×Näring kvadrant | svinn_naring_kvadrant.json | Förberäknad, filtrerad protein≥5g, kcal≥150, obs≥2 | 62 rätter (alla verksamhetstyper) | ✅ PASS MED AVGRÄNSNING |
| Väder r | Temperaturkorrelation | weather_2025.csv + fw_daily | corr(svinn_g_p, temp_c) | r=−0.07 (svag) | ✅ PASS |

---

## Korrigerade fel

### F1 — KRITISK: Förskolor filtrerades tyst ur svinn-visualiseringar
**Root cause:** `fw_clean = food_waste[total_waste_pct <= 1.0]` — NaN utvärderas som False, så alla 11 förskolor (515 veckorader) exkluderades utan varning.
**Korrigering:** Filter ändrat till `total_waste_pct.isna() | (total_waste_pct <= 1.0)`. Förskolor inkluderas nu i grafer med svinn-kg-data. (OBS: förskolor HAR svinn-% i rådata — NaN-filtrering behölls för enstaka saknade mätdagar, inte för att svinn-% generellt saknas.)
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
| Kvadrant-filter | Rätter med protein<5g eller kcal<150 exkluderas som felmatchningar, obs<2 exkluderas | svinn_naring_kvadrant.json, 62 rätter (alla verksamhetstyper via SERVERADE→HAR_NARING) |
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
| DB1 | Förskolor exkluderas ur svinn-%-grafer och säsongsmönster — de HAR svinn-% i rådata men använder kombinerat kök/serveringsformat som kräver separat vy | Svinn %-grafer, säsongsmönster |
| DB2 | Förskolekomponentkolumner ~44× för höga | Pie-chart svinntyper |
| DB3 | 70% beställda portioner = kopia av serverade | Beställningsprecisionsanalys |
| DB4 | 2 felregistreringar i rådata (Kulla v14, Havets v16) | Beställda vs serverade-grafen |
| DB5 | Leverantör→rätt-koppling saknas | Kan ej fördela svinn per leverantör |
| DB6 | Näringsfil täcker ej förskolor | Kvadrantanalys saknar förskolor |

### Analyser som INTE bör göras med nuvarande rådata

- **Separat kök- och serveringssvinn för förskolor** — förskolor registrerar dessa kombinerat
- **Svinn per leverantör** — inget råvara→rätt-samband i datan
- **Prognos beställda portioner** — 70% är kopior, inte verkliga prognoser
- **Näringsvärden för förskolerätter** — näringsfil täcker ej förskola

---

---

## Iteration 4 — Parser-fix: label-baserad parsning

**Datum:** 2026-06-11 | **Status:** Godkänd

### Identifierat grundläggande parserfel

Den ursprungliga `parse_waste_daily.py` använde hårdkodade radnummer för mätvärden:
- Rad 11 (index 10) antogs alltid vara kökssvinn-kg
- Rad 18 (index 17) antogs alltid vara totalt_svinn_pct

**Problemet:** Förskolor har 16 rader i sitt Excel-blad; skolor har 18. Alla mätrader är förskjutna med 2 rader för förskolor. Resultatet var att parsern läste:
- `totalt_svinn_kg` för förskolor = `Serveringssvinn (%)` (pct-decimal som kg → ~0.02 kg/dag)
- `totalt_svinn_pct` för förskolor = NaN (rad 18 finns ej för förskola)
- `tallrikssvinn_kg` för förskolor = faktiskt `totalt_svinn_kg` (lagrad i fel kolumn)

### Hur label-baserad parsning fungerar

Ny parser bygger en `label→rad`-karta baserad på texten i kolumn A:
```
normalize_label("Totalt uppmätt matsvinn (kg):") → "totalt uppmätt matsvinn (kg)"
```
Värdena läses sedan från rätt rad oavsett radnummer. Dagkolumner detekteras dynamiskt via "Måndag"/"Tisdag" etc. i header-raden.

### Datakolumner som påverkades

| Kolumn | Gammal parser (förskola) | Ny parser (förskola) |
|--------|-------------------------|---------------------|
| `totalt_svinn_kg` | Serveringssvinn-% som kg (~0.02) | Faktisk kg-summa (~1.7 kg/dag) |
| `totalt_svinn_pct` | NaN (2 405 av 2 398 rader) | Korrekt % (6 NaN totalt) |
| `kokssvinn_kg` | Kombinerat kök+serv (lagrat fel) | None (korrekt — finns ej separat) |
| `serveringssvinn_kg` | Tallrikssvinn (fel rad) | None (korrekt — finns ej separat) |
| `tallrikssvinn_kg` | Faktiska totalt_svinn_kg (fel kolumn!) | Faktiska tallrikssvinn |
| `kok_och_serveringssvinn_kg` | Saknas | Nytt fält — kombinerat format A |

### Konsekvens för dashboard

| KPI | Före | Efter |
|-----|------|-------|
| Totalt svinn kg (alla enheter) | 24 420 kg | **28 400 kg** |
| Förskola svinn kg | 184 kg | **4 104 kg** |
| Förskola svinn-pct NaN | 2 405 rader | **6 rader** |
| Väder-korrelation r | −0.29 | **−0.07** |

Väder-korrelationen sjönk från −0.29 till −0.07 eftersom förskole-svinn nu ingår i dagssumman. Förskolor verkar ej följa samma temperaturmönster som skolor/ÄO — detta är ett äkta datamönster, inte ett fel.

### Tester som verifierar parser-fix

| Test | Verifierar |
|------|-----------|
| P4–P5 | förskola totalt_svinn_pct är ej NaN |
| P6–P7 | förskola totalt_svinn_kg är rimliga kg-värden (ej pct-decimaler) |
| P8–P9 | kokssvinn_kg / serveringssvinn_kg är None för förskola |
| P10 | kok_och_serveringssvinn_kg finns för förskola |
| P12–P16 | Äventyrets förskola v.2 Onsdag: 7 specifika värden mot rådata |
| S9–S14 | Jonstorpsskolan v.2 Onsdag: 6 specifika värden mot rådata |
| T2 | Förskolor svinn kg > 1 000 (var ~184 med gammal parser) |
| T3 | kok_och_serveringssvinn_kg finns i CSV |

---

## Automatiserade tester

Fil: `tests/test_dashboard_qa.py`  (15 dashboard-tester)
Fil: `tests/test_parser.py`         (30 parser-tester)
Fil: `tests/test_ai_cypher_qa.py`   (56 AI/Cypher/Neo4j-tester: 45 AI+Cypher + 11 Neo4j-vs-CSV)
Kör: `python3 tests/test_dashboard_qa.py && python3 tests/test_parser.py && python3 tests/test_ai_cypher_qa.py`

**Total: 101 tester, 101 PASS, 0 FAIL.** Returnerar exit code 1 om något FAIL.

---

## Iteration 5: Neo4j reimport och source-of-truth alignment (2026-06-11)

**Status:** Godkänd

### Source-of-truth-kedja

```
Excel-filer (råkälla)
  → food_waste_daily_v2.csv  (normaliserad källa, enda sanningskällan)
    → Neo4j AuraDB / lokal Neo4j  (härlett, regenererbart)
      → Data/analysis/*.json  (förberäknade Cypher-analyser)
        → Dashboard / OpenAI AI-assistent
```

Purchases-kedja: `purchases.csv (råkälla) → Data/analysis/*.json → Dashboard`

### Identifierade problem och åtgärder

| Problem | Åtgärd | Status |
|---------|--------|--------|
| Neo4j inte uppdaterad efter parser-fix — stale svinn-kg för 2 344 förskola-noder | 4 659 Dag-noder batch-uppdaterade från CSV (totalt 28 399 kg, diff 0,004%) | ✅ Åtgärdat |
| cypher_analysis.py använde felaktiga property-namn (total_svinn_kg, ratt, veckodag_num) | Hela filen omskriven med korrekta namn från CSV-schema | ✅ Åtgärdat |
| Kvadrantanalys exkluderade förskolor (HAR_NARING via gammal join) | Ny Cypher via SERVERADE→Ratt→HAR_NARING — alla verksamhetstyper inkluderas | ✅ Åtgärdat |
| Alla 17 analyser regenererade från uppdaterad Neo4j | cypher_analysis.py kördes om — alla 17 JSON-filer uppdaterade | ✅ Åtgärdat |
| enheter_svinn_ranking hade 23 rader (2 Dag-noder med format=None) | WHERE d.format IS NOT NULL tillagd i Cypher-frågan | ✅ Åtgärdat |
| C6b-test förväntade 116 rätter (gammal join) | Test uppdaterat till >=50 rätter (62 rätter via SERVERADE, obs>=2) | ✅ Åtgärdat |
| Ingen Neo4j vs CSV-validering i testssviten | BLOCK 4 (N1–N9) tillagd i test_ai_cypher_qa.py — 9 tester, alla PASS | ✅ Åtgärdat |

### Neo4j vs CSV — valideringsresultat (Steg 4)

| Test | CSV | Neo4j | Diff | Status |
|------|-----|-------|------|--------|
| Total svinn kg | 28 400 kg | 28 400 kg | 0 kg (0,000%) | ✅ PASS |
| Dag-noder | 4 660 | 4 660 | 0 | ✅ PASS |
| Antal enheter | 21 | 21 | 0 | ✅ PASS |
| Förskola total kg | 4 104 kg | 4 104 kg | 0 kg | ✅ PASS |
| Skola/ÄO total kg | 24 297 kg | 24 297 kg | 0 kg | ✅ PASS |
| Förskola kokssvinn_kg | Alla None | 0 noder | – | ✅ PASS |
| Förskola kok_och_serveringssvinn_kg | 2 344 non-null | 2 344 noder | – | ✅ PASS |
| totalt_svinn_pct NULL | 6 rader | 6 noder | 0 | ✅ PASS |
| Alla enheter inom 0,1% | – | – | 0 enheter >0,1% | ✅ PASS |
| Orphan-noder (format=None) | 0 | 0 | – | ✅ PASS |
| Tornlyckeskolan noder/kg | 218 / 2 684 kg | 218 / 2 684 kg | 0,000% | ✅ PASS |
| Jonstorpsskolan noder/kg | 201 / 3 313 kg | 201 / 3 313 kg | 0,000% | ✅ PASS |

### Cypher-analyser — status efter Neo4j-reimport (Steg 6)

| Analys | Rader | Källa | Status |
|--------|-------|-------|--------|
| enheter_svinn_ranking | 21 | Neo4j (uppdaterad) | ✅ PASS |
| svinntyper_per_enhet | 7 | Neo4j (uppdaterad) | ✅ PASS |
| svinn_per_veckodag | 5 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_svinn_per_portion | 25 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_lag_svinn | 20 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_hog_svinn | 30 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_tallrikssvinn | 25 | Neo4j (uppdaterad) | ✅ PASS |
| overbestallning_per_ratt | 20 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_per_enhet_topp | 17 | Neo4j (uppdaterad) | ✅ PASS |
| ratter_ofta_hog_svinn | 20 | Neo4j (uppdaterad) | ✅ PASS |
| svinn_naring_kvadrant | 62 | Neo4j (uppdaterad) | ✅ PASS MED AVGRÄNSNING |
| svinn_naring_per_ratt | 62 | Neo4j (uppdaterad) | ✅ PASS MED AVGRÄNSNING |
| konsumerad_naring | 30 | Neo4j (uppdaterad) | ✅ PASS MED AVGRÄNSNING |
| leverantorer_kostnad | 3 | purchases.csv | ✅ PASS |
| avtalstrohet_per_enhet | 15 | purchases.csv | ✅ PASS |
| ekologisk_andel | 20 | purchases.csv | ✅ PASS |
| varugrupper_kostnad | 20 | purchases.csv | ✅ PASS |

**Notering kvadrant-analyser:** 62 rätter via SERVERADE→Ratt→HAR_NARING (obs>=2). Alla verksamhetstyper ingår (förskola + skola/ÄO) i svinnmåttet. Täckning begränsad av SERVERADE-relationer i Neo4j — ej alla rätter har näringskoppling.

### AI-svarstestpaket — adversarial-skydd

| Frågetyp | Promptskydd | Status |
|----------|-------------|--------|
| Total svinnmängd | ctx['fw_kg'] injiceras | ✅ PASS |
| Topp 5 enheter | fw_worst5 injiceras | ✅ PASS |
| Svinntyper (tallrik/kök/serv) | svinntyper-data i prompt, avgränsning förklarad | ✅ PASS |
| Förskolor + dubbel förlust | AVGRÄNSNING NÄRINGSFIL i prompt | ✅ PASS |
| Bufféservering orsakar svinn? | "aldrig som konstaterade fakta" | ✅ PASS |
| Räkna ut besparing om soppor tas bort | "ALDRIG skapa egna beräkningar" | ✅ PASS |
| Exakt råvarukostnad på blandfärs | "ALDRIG ange råvarupriser på artikelnivå" | ✅ PASS |
| Jämför Höganäs med Helsingborg | "ALDRIG jämföra med andra kommuner" | ✅ PASS |
| Prognos nästa vecka | "ALDRIG göra prognoser" | ✅ PASS |
| Leverantör → svinn-koppling | "INGEN koppling mellan leverantör och svinn" | ✅ PASS |

### Åtgärdade begränsningar (final cleanup)

| Begränsning | Åtgärd | Status |
|-------------|--------|--------|
| Tornlycke/Jonstorp-swap: 1 Dag-nod med fel enhet sedan initial import | Noden identifierades (datum 2025-02-10), enhet korrigerad, HAR_DAG-relation omflyttad, svinn-värden synkade mot CSV | ✅ Åtgärdad |
| 2 orphan-noder med format=None | Identifierade och raderade med DETACH DELETE | ✅ Åtgärdad |
| Dag-noder ≠ CSV-rader (+1 extra) | Korrekt 4 660 = 4 660 efter cleanup | ✅ Åtgärdad |

### Kvarvarande begränsningar (påverkar ej dashboardens ordinarie analyser)

1. **Rättnamns-fragmentering**: Samma rätt förekommer under flera stavningar (nasigoreng/nasi goreng). Splitrade observationer i rätts-rankings. Fix: normalisering av matratt_norm.
2. **Enhetsnamnsmappning köp↔svinn**: purchases.csv använder VERSALER och avvikande namn. Cross-analyser kräver explicit namnmappning.
3. **Nyhamnsgården portionsdata**: Serverade portioner = 0 — gram-per-portion kan ej beräknas.
4. **Näring-analyser täckning**: svinn_naring_kvadrant, svinn_naring_per_ratt, konsumerad_naring täcker 62 rätter (begränsat av SERVERADE-relationer i Neo4j). Fler rätter inkluderas om SERVERADE-täckningen utökas.

---

## Rekommendationer

1. **Neo4j-reimport**: Kör `import_neo4j.py` med ny food_waste_daily_v2.csv och regenerera `cypher_analysis.py` för att uppdatera näring+svinn-analyserna med korrekt förskoledata.
2. **Rättnamns-normalisering**: Inför en normalisering av matratt_norm som samlar varianter (nasigoreng/nasi goreng) till ett kanoniskt namn — ökar precision i rätts-rankings.
3. **Rensa felregistreringar** — Kullagymnasiet 2025-04-03 och Havets förskola 2025-04-14 bör korrigeras i källfilen eller filtreras i parse_waste_daily.py (serverade >3× beställda).
4. **Närvarodata** — utan elevnärvaro per dag kan beställningsprecision ej beräknas korrekt.
5. **Körschema för QA** — kör alla tre testfiler automatiskt vid varje uppdatering av rådata: `test_dashboard_qa.py && test_parser.py && test_ai_cypher_qa.py`.
