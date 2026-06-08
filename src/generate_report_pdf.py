# -*- coding: utf-8 -*-
"""
Skolmåltidsrapport -- Höganäs kommun 2025.
Struktur per manus rekommendation: svinn och styrning i fokus, inköp som ekonomisk konsekvens.
"""
from __future__ import annotations
import io
import os
from pathlib import Path
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _register_fonts():
    """Registrera DejaVu Sans (medföljer matplotlib) för full Unicode/svenska tecken."""
    import matplotlib
    ttf_dir = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
    fonts = {
        "DejaVu":       ttf_dir / "DejaVuSans.ttf",
        "DejaVu-Bold":  ttf_dir / "DejaVuSans-Bold.ttf",
        "DejaVu-Oblique": ttf_dir / "DejaVuSans-Oblique.ttf",
    }
    for name, path in fonts.items():
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    return "DejaVu" if (ttf_dir / "DejaVuSans.ttf").exists() else "Helvetica"

FONT = _register_fonts()
FONT_BOLD    = f"{FONT}-Bold"    if FONT == "DejaVu" else "Helvetica-Bold"
FONT_OBLIQUE = f"{FONT}-Oblique" if FONT == "DejaVu" else "Helvetica-Oblique"

BASE      = Path(__file__).resolve().parent.parent
PROCESSED = BASE / "data" / "processed"
REPORTS   = BASE / "reports"

BLUE_DARK   = colors.HexColor("#1e3a5f")
BLUE_MID    = colors.HexColor("#2563eb")
BLUE_LIGHT  = colors.HexColor("#dbeafe")
GREEN       = colors.HexColor("#16a34a")
GREEN_LIGHT = colors.HexColor("#dcfce7")
RED         = colors.HexColor("#dc2626")
RED_LIGHT   = colors.HexColor("#fee2e2")
AMBER       = colors.HexColor("#d97706")
AMBER_LIGHT = colors.HexColor("#fef3c7")
GRAY_DARK   = colors.HexColor("#374151")
GRAY_MID    = colors.HexColor("#6b7280")
GRAY_LIGHT  = colors.HexColor("#f3f4f6")
WHITE       = colors.white
PAGE_W, PAGE_H = A4

plt.rcParams.update({
    "font.family":"DejaVu Sans","font.size":10,
    "axes.spines.top":False,"axes.spines.right":False,
    "axes.grid":True,"grid.alpha":0.3,"grid.linestyle":"--",
})

def fig_to_img(fig, w=16, h=7):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0); plt.close(fig)
    return Image(buf, width=w*cm, height=h*cm)

def load():
    fw  = pd.read_parquet(PROCESSED/"food_waste_daily.parquet")
    fww = pd.read_parquet(PROCESSED/"food_waste.parquet")
    pur = pd.read_parquet(PROCESSED/"purchases.parquet")
    mn  = pd.read_parquet(PROCESSED/"menu_nutrition.parquet")
    return fw, fww, pur, mn

# ── GRAFER ────────────────────────────────────────────────────────────────────

def chart_waste_chain():
    """Kap 2: Var i kedjan uppstar svinnet? (manus-verifierade siffror)"""
    cats     = ["Forskola\n(personal portionerar)",
                "Skola/Gymnasium\n(sjalvservering)",
                "Aldreomsorg\n(personal portionerar)"]
    plate    = [34, 68, 39]
    nonplate = [66, 32, 61]
    fig, ax = plt.subplots(figsize=(10,5))
    x = np.arange(3); w = 0.5
    b1 = ax.bar(x, plate,    w, color="#2563eb", alpha=0.9, label="Tallrikssvinn")
    b2 = ax.bar(x, nonplate, w, bottom=plate, color="#94a3b8", alpha=0.7, label="Koks/serveringssvinn")
    for bar, val in zip(b1, plate):
        ax.text(bar.get_x()+bar.get_width()/2, val/2, f"{val}%",
                ha="center", va="center", color="white", fontweight="bold", fontsize=14)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=10)
    ax.set_ylabel("Andel av uppmattt svinn (%)"); ax.set_ylim(0,115)
    ax.legend(fontsize=9)
    ax.set_title("Var uppstar svinnet? Tallrikssvinnets andel per verksamhetstyp",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig_to_img(fig, 16, 6)

def chart_waste_per_unit():
    """Kap 1: Svinn per enhet"""
    units  = ["Kullagymnasiet","Tornlyckeskolan","Eric Ruuths fsk","Svanebacks fsk",
              "Lerbergsskolan","Revets fsk","Nyhamnsskolan","Vikenskolan",
              "Klovera. fsk","Jonstorpsskolan","Havets fsk","Larlyckan fsk",
              "Bruksskolan","Aventyrets fsk","Vikens Ry fsk","Vasbyhemmet",
              "Eleshults fsk","Peter Lundhs fsk","Vikhaga"]
    wpp    = [0.0521,0.0498,0.0479,0.0479,0.0459,0.0457,0.0447,0.0406,
              0.0381,0.0352,0.0349,0.0348,0.0301,0.0283,0.0229,0.0207,
              0.0186,0.0164,0.0125]
    def col(n):
        if "gymnasium" in n.lower(): return "#7c3aed"
        if "fsk" in n.lower():       return "#16a34a"
        if "vasb" in n.lower() or "haga" in n.lower(): return "#ea580c"
        return "#2563eb"
    fig, ax = plt.subplots(figsize=(10,8))
    bars = ax.barh(range(len(units)), wpp, color=[col(u) for u in units], alpha=0.88)
    ax.axvline(0.05, color="#dc2626", linestyle="--", lw=1.5, label="Referenslinje 0,05 kg*")
    ax.set_yticks(range(len(units))); ax.set_yticklabels(units, fontsize=9)
    ax.set_xlabel("Svinn per serverad portion (kg)")
    ax.set_title("Svinn per enhet (Solglantans forskola exkluderad -- ofullstandig data)",
                 fontsize=11, fontweight="bold")
    for bar, val in zip(bars, wpp):
        ax.text(val+0.0003, bar.get_y()+bar.get_height()/2, f"{val:.4f}", va="center", fontsize=8)
    ax.legend(handles=[
        mpatches.Patch(color="#7c3aed",label="Gymnasium"),
        mpatches.Patch(color="#2563eb",label="Grundskola"),
        mpatches.Patch(color="#16a34a",label="Forskola"),
        mpatches.Patch(color="#ea580c",label="Aldreomsorg"),
        plt.Line2D([0],[0],color="#dc2626",linestyle="--",label="Ref. 0,05 kg*"),
    ], loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig_to_img(fig, 16, 9)

def chart_overorder():
    """Kap 3: Bestaallningsprecision"""
    units  = ["Kullagymnasiet","Lerbergsskolan","Bruksskolan\n(oviktat ~17%)","Vikenskolan","Nyhamnsskolan"]
    values = [21.1, 13.7, 11.9, 5.3, 4.8]
    cols   = ["#dc2626","#f59e0b","#f59e0b","#16a34a","#16a34a"]
    fig, ax = plt.subplots(figsize=(9,4.5))
    bars = ax.bar(range(5), values, color=cols, alpha=0.88, width=0.55)
    ax.axhline(5, color="#6b7280", linestyle="--", lw=1.2, label="5%-mal")
    ax.set_xticks(range(5)); ax.set_xticklabels(units, fontsize=9)
    ax.set_ylabel("Genomsnittlig overbestaallning, viktad (%)")
    ax.set_title("Bestaallningsprecision -- genomsnittlig overbestaallning",
                 fontsize=12, fontweight="bold")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                f"{val:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax.legend(fontsize=9); fig.tight_layout()
    return fig_to_img(fig, 14, 5.5)

def chart_menu_waste(mn, fww):
    """Kap 5: Menyacceptans -- veckor med hogst/lagst svinn"""
    fww_c = fww.copy()
    for c in ["total_waste_kg","served_portions","week"]:
        fww_c[c] = pd.to_numeric(fww_c[c], errors="coerce")
    fww_c = fww_c[(fww_c["served_portions"]>10) & fww_c["total_waste_kg"].notna() & fww_c["week"].notna()]
    fww_c["wpp"] = fww_c["total_waste_kg"] / fww_c["served_portions"]
    fww_c = fww_c[fww_c["wpp"]<1]
    fw_week = fww_c.groupby("week")["wpp"].mean()

    skola = mn[(mn["menu_type"]=="skola") & (mn["dish_type"]=="dagens_lunch")].copy()
    skola["week"] = pd.to_numeric(skola["week"], errors="coerce")
    skola_week = skola.groupby("week")["dish_name"].apply(
        lambda x: " | ".join(x.dropna().unique()[:3])
    ).reset_index()

    merged = fw_week.reset_index().merge(skola_week, on="week", how="inner")
    merged = merged.sort_values("wpp", ascending=False)
    top5   = merged.head(5)
    bot5   = merged.tail(5).sort_values("wpp")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.5))
    for ax, data, color, title in [
        (ax1, top5,  "#dc2626", "Veckor med HOGST svinn"),
        (ax2, bot5,  "#16a34a", "Veckor med LAGST svinn"),
    ]:
        labels = [f"v.{int(w)}" for w in data["week"]]
        bars = ax.barh(range(len(data)), data["wpp"].values, color=color, alpha=0.88)
        ax.set_yticks(range(len(data))); ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel("Svinn kg/portion"); ax.set_title(title, fontsize=11, fontweight="bold", color=color)
        for bar, val in zip(bars, data["wpp"].values):
            ax.text(val+0.0003, bar.get_y()+bar.get_height()/2, f"{val:.4f}", va="center", fontsize=8)
    fig.suptitle("Menyacceptans -- svinn per vecka kopplat till veckans ratter",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig_to_img(fig, 15, 5.5)

def chart_waste_cost(pur, fww):
    """Kap 6: Vad kostar svinnet?"""
    fww_c = fww.copy()
    for c in ["total_waste_pct","served_portions"]:
        fww_c[c] = pd.to_numeric(fww_c[c], errors="coerce")
    avg_pct = fww_c[(fww_c["total_waste_pct"].notna()) & (fww_c["total_waste_pct"]<1) &
                    (fww_c["served_portions"]>10)]["total_waste_pct"].mean()

    pur_c = pur[pur["unit_name_std"].notna()].copy()
    pur_c["kronor"] = pd.to_numeric(pur_c["kronor"], errors="coerce")
    vg = pur_c.groupby("varugrupp")["kronor"].sum().reset_index()
    vg.columns = ["varugrupp","total_kr"]
    vg["waste_kr"] = vg["total_kr"] * avg_pct
    vg = vg[vg["total_kr"]>80000].sort_values("waste_kr", ascending=True).tail(10)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.barh(range(len(vg)), vg["waste_kr"].values/1000,
                   color="#dc2626", alpha=0.78)
    ax.set_yticks(range(len(vg)))
    ax.set_yticklabels([v[:32] for v in vg["varugrupp"]], fontsize=9)
    ax.set_xlabel(f"Uppskattad svinnkostnad (tkr) -- antar {avg_pct*100:.1f}% genomsnittligt svinn")
    ax.set_title("Vad kostar svinnet? -- uppskattad svinnkostnad per varugrupp",
                 fontsize=12, fontweight="bold")
    for bar, val in zip(bars, vg["waste_kr"].values/1000):
        ax.text(val+0.3, bar.get_y()+bar.get_height()/2,
                f"{val:.0f} tkr", va="center", fontsize=9)
    fig.tight_layout()
    return fig_to_img(fig, 15, 6.5), avg_pct

# ── STYLES ────────────────────────────────────────────────────────────────────
def styles():
    s = {}
    def ps(name, **kw):
        defaults = dict(fontName=FONT, fontSize=10, textColor=GRAY_DARK,
                        leading=14, spaceAfter=4)
        defaults.update(kw); s[name] = ParagraphStyle(name, **defaults)
    ps("h1", fontName=FONT_BOLD, fontSize=18, textColor=BLUE_DARK,
       leading=22, spaceBefore=14, spaceAfter=6)
    ps("h2", fontName=FONT_BOLD, fontSize=13, textColor=BLUE_MID,
       leading=17, spaceBefore=12, spaceAfter=5)
    ps("h3", fontName=FONT_BOLD, fontSize=11, leading=15, spaceBefore=9, spaceAfter=4)
    ps("body", leading=15, spaceAfter=5, alignment=TA_JUSTIFY)
    ps("bold", fontName=FONT_BOLD, leading=15)
    ps("cap",  fontName=FONT_OBLIQUE, fontSize=8, textColor=GRAY_MID,
       leading=11, spaceAfter=8, alignment=TA_CENTER)
    ps("src",  fontSize=8, textColor=GRAY_MID, leading=11, spaceAfter=3)
    ps("note", fontName=FONT_OBLIQUE, fontSize=9, textColor=GRAY_MID, leading=12)
    ps("foot", fontSize=8, textColor=GRAY_MID, leading=11, alignment=TA_CENTER)
    ps("ib_t", fontName=FONT_BOLD, fontSize=11, textColor=BLUE_DARK, leading=14)
    ps("ib_b", leading=14)
    ps("rec_t", fontName=FONT_BOLD, fontSize=11, textColor=WHITE, leading=14)
    ps("rec_b", leading=14)
    ps("chap", fontName=FONT_BOLD, fontSize=10, textColor=WHITE, leading=14)
    return s

def box(title, body, s, bg=BLUE_LIGHT):
    t = Table([[Paragraph(title, s["ib_t"])],[Paragraph(body, s["ib_b"])]],
              colWidths=[16.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#f8fafc")),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),
        ("BOX",(0,0),(-1,-1),1,colors.HexColor("#e2e8f0")),
        ("LINEBELOW",(0,0),(-1,0),1,colors.HexColor("#cbd5e1")),
    ]))
    return t

def mbox(text, s):
    t = Table([[Paragraph(text, s["src"])]], colWidths=[16.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),GRAY_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),
        ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#cbd5e1")),
    ]))
    return t

def dtbl(headers, rows, s, widths=None):
    w = widths or [16.4*cm/len(headers)]*len(headers)
    data = [[Paragraph(f"<b>{h}</b>", s["src"]) for h in headers]]
    data += [[Paragraph(str(c), s["src"]) for c in row] for row in rows]
    t = Table(data, colWidths=w)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),BLUE_DARK),("TEXTCOLOR",(0,0),(-1,0),WHITE),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,GRAY_LIGHT]),
        ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#cbd5e1")),
        ("INNERGRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
        ("ALIGN",(1,1),(-1,-1),"RIGHT"),
    ]))
    return t

def chap_header(nr, title, s):
    t = Table([[
        Paragraph(f"<b>{nr}</b>",
            ParagraphStyle("cn",fontName="Helvetica-Bold",fontSize=18,
                           textColor=WHITE,alignment=TA_CENTER)),
        Paragraph(title, s["h2"])
    ]], colWidths=[1.2*cm, 15.2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),BLUE_DARK),
        ("BACKGROUND",(1,0),(-1,-1),BLUE_LIGHT),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(-1,-1),10),
        ("BOX",(0,0),(-1,-1),0,WHITE),
    ]))
    return t

def rec_box(code, prio, title, body, s, bg):
    t = Table([
        [Paragraph(f"<b>{code}   {prio}</b>", s["rec_t"])],
        [Paragraph(f"<b>{title}</b>", s["ib_t"])],
        [Paragraph(body, s["rec_b"])],
    ], colWidths=[16.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#f8fafc")),
        ("BACKGROUND",(0,2),(-1,-1),WHITE),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14),
        ("BOX",(0,0),(-1,-1),1,colors.HexColor("#e2e8f0")),
    ]))
    return t

def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BLUE_DARK)
    canvas.rect(0,PAGE_H-1.2*cm,PAGE_W,1.2*cm,fill=1,stroke=0)
    canvas.setFillColor(WHITE); canvas.setFont(FONT, 8)
    canvas.drawString(1.5*cm, PAGE_H-0.8*cm,
                      "Höganäs kommun — Skolmåltidsanalys 2025")
    canvas.drawRightString(PAGE_W-1.5*cm, PAGE_H-0.8*cm, "KONFIDENTIELLT")
    canvas.setFillColor(GRAY_MID); canvas.setFont(FONT, 8)
    canvas.drawCentredString(PAGE_W/2, 0.8*cm, f"Sida {doc.page}")
    canvas.setFillColor(colors.HexColor("#e2e8f0"))
    canvas.rect(1.5*cm,1.1*cm,PAGE_W-3*cm,0.04*cm,fill=1,stroke=0)
    canvas.restoreState()

# ── BUILD ─────────────────────────────────────────────────────────────────────
def build():
    fw, fww, pur, mn = load()
    s = styles()
    out = REPORTS / "Höganäs_Skolmåltidsanalys_2025.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2.4*cm, bottomMargin=2*cm)
    story = []

    # ── OMSLAG ────────────────────────────────────────────────────────────────
    cover = Table([[
        Paragraph("Skolmåltidsanalys<br/>Höganäs kommun 2025",
            ParagraphStyle("ct", fontName=FONT_BOLD, fontSize=26,
                           textColor=WHITE, leading=32))
    ]], colWidths=[16.4*cm], rowHeights=[5*cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),BLUE_DARK),
        ("LEFTPADDING",(0,0),(-1,-1),24),
        ("TOPPADDING",(0,0),(-1,-1),34),
        ("BOTTOMPADDING",(0,0),(-1,-1),20),
    ]))
    story.append(cover)
    story.append(Spacer(1,0.4*cm))
    sub = Table([[Paragraph(
        "Svinn och styrning i maltidskedjan -- fran planering till tallrik<br/><br/>"
        f"<font color='#6b7280'>Datum: {date.today().strftime('%d %B %Y')}   |   "
        "Data: Hoganas kostverksamhet 2025   |   Analys: Konkret Advisory   |   "
        "Utvalda fynd granskade mot oberoende tabeller: manus.im</font>",
        s["body"]
    )]], colWidths=[16.4*cm])
    sub.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),BLUE_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12),
        ("LEFTPADDING",(0,0),(-1,-1),16),
        ("BOX",(0,0),(-1,-1),1,BLUE_MID),
    ]))
    story.append(sub)
    story.append(PageBreak())

    # ── SAMMANFATTNING ────────────────────────────────────────────────────────
    story.append(Paragraph("Sammanfattning", s["h1"]))
    story.append(HRFlowable(width="100%",thickness=2,color=BLUE_MID,spaceAfter=10))
    story.append(Paragraph(
        "Hoganas har inte bara ett matsvinnsproblem -- det ar ett <b>styrningsproblem i kedjan "
        "mellan planering, bestaallning, servering och konsumtion</b>. "
        "Datan visar att pengar forsvinner nar mat bestaalls i storre volym an vad som serveras, "
        "nar elever tar mer an de ater upp, och nar vissa ratter eller serveringssituationer "
        "skapar hogre tallrikssvinn. "
        "Inkopsdata anvands for att vardera vilka svinnfloden som ar ekonomiskt viktigast.",
        s["body"]
    ))
    story.append(Spacer(1,0.3*cm))

    # Tre nyckelinsikter
    for nr, bg, title, body_text in [
        ("1", BLUE_MID,
         "Var i kedjan? -- Tallrikssvinnet dominerar i skolan",
         "I skola och gymnasium utgor tallrikssvinnet 68 % av det uppmaatta svinnet "
         "(mot 34 % i forskola). Datan indikerar ett starkt samband med att eleverna tar "
         "maten sjalva -- men sambandet ar observationellt och kraver ett kontrollerat test."),
        ("2", AMBER,
         "Bestaallningar -- Kullagymnasiet och Lerbergsskolan overbestaaller systematiskt",
         "Kullagymnasiet overbestaaller i viktat snitt 21 %, Lerbergsskolan 13,7 %. "
         "Kullagymnasiet vecka 10: 2 580 bestaallda portioner, 1 557 serverade -- 39,7 % for mycket. "
         "Det ar mat som kops, lagas och sedan inte ater."),
        ("3", RED,
         "Inkop -- Vasbyhemmet koper 30 % utanfor avtal",
         "Vasbyhemmet, Vikhaga och Nyhamnsgarden har hogst andel inkop utanfor upphandlat avtal "
         "(30 %, 18 % respektive 16 %). Flaggat av kommunens eget upphandlingssystem. "
         "Vasbyhemmet: indikativt ~680 tkr i avvikelse per ar."),
    ]:
        row = Table([
            [Paragraph(f"<b>{nr}</b>",
                ParagraphStyle("n",fontName="Helvetica-Bold",fontSize=18,
                               textColor=WHITE,alignment=TA_CENTER)),
             Table([[Paragraph(f"<b>{title}</b>",s["ib_t"])],
                    [Paragraph(body_text,s["ib_b"])]],colWidths=[13*cm])]
        ], colWidths=[1.5*cm,13*cm])
        row.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(0,-1),bg),
            ("BACKGROUND",(1,0),(-1,-1),
             BLUE_LIGHT if bg==BLUE_MID else AMBER_LIGHT if bg==AMBER else RED_LIGHT),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
            ("LEFTPADDING",(0,0),(-1,-1),10),
            ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#cbd5e1")),
        ]))
        story.append(row); story.append(Spacer(1,0.3*cm))

    story.append(PageBreak())

    # ── KAP 1: VAD VISAR SVINNDATAN ───────────────────────────────────────────
    story.append(chap_header("1","Vad visar svinndatan?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Svinnet registreras veckovis per enhet uppdelat pa kokssvinn, serveringssvinn och "
        "tallrikssvinn. Nedanstaande visar genomsnittligt svinn per serverad portion.",
        s["body"]
    ))
    story.append(chart_waste_per_unit())
    story.append(Paragraph(
        "Figur 1. Svinn per serverad portion per enhet. Referenslinjen 0,05 kg anvands som "
        "branschjamforelseniva -- det ar inte en officiellt publicerad maxgrans. "
        "Solglantans forskola exkluderas p.g.a. ofullstandig portionsdata. "
        "Kalla: Matsvinn 2025 [1].", s["cap"]
    ))
    story.append(PageBreak())

    # ── KAP 2: VAR I KEDJAN ───────────────────────────────────────────────────
    story.append(chap_header("2","Var i kedjan uppstar svinnet?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Svinnets sammansattning skiljer sig kraftigt mellan verksamhetstyper. "
        "Det observerade monstret samvarierar med hur maten serveras.",
        s["body"]
    ))
    story.append(chart_waste_chain())
    story.append(Paragraph(
        "Figur 2. Tallrikssvinnets andel av totalt uppmattt svinn per verksamhetstyp. "
        "Siffror verifierade mot oberoende tabeller [8]: forskola 34 %, skola/gymnasium 68 %, "
        "aldreomsorg 39 %. Kalla: Matsvinn 2025 [1]. "
        "Serveringssattet ar hartlett fran verksamhetstyp -- inte direkt registrerat.",
        s["cap"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(box(
        "Observerat samband -- inte bevisad orsak",
        "I forskolan portionerar personal maten, i grundskolan tar eleverna sjalva. "
        "Datan indikerar ett starkt samband: 68 % vs 34 % tallrikssvinn. "
        "Sambandet ar konsekvent men observationellt -- kausal slutsats kraver ett kontrollerat test "
        "(se rekommendation R3).", s, BLUE_LIGHT
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(box(
        "Kokstyp forstarker bilden",
        "Mottagningskoks (tar emot fardignlagad mat) har 43 % lagre tallrikssvinn an "
        "tillagningskoks (lagar sjalva). De kan inte overcook -- maten anland i "
        "forkontrollerade mangder. Det satter ytterligare fokus pa koksvolymen som styrningsproblem.",
        s, GREEN_LIGHT
    ))
    story.append(PageBreak())

    # ── KAP 3: BESTAALLNINGSPRECISION ────────────────────────────────────────
    story.append(chap_header("3","Bestaaller vi ratt mangd?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Skillnaden mellan bestaallda och serverade portioner visar om koken bestaaller "
        "ratt volym. En systematisk overbestaallning indikerar att mat planeras och/eller "
        "bestaalls i storre mangd an vad som faktiskt serveras.",
        s["body"]
    ))
    story.append(chart_overorder())
    story.append(Paragraph(
        "Figur 3. Viktad genomsnittlig overbestaallning (%). Bruksskolan: viktat 11,9 %, "
        "oviktat ~17 %. Verifierat mot oberoende tabeller [8]. Kalla: Matsvinn 2025 [1].",
        s["cap"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(dtbl(
        ["Enhet","Viktat snitt","Max en vecka","Konkret exempel"],
        [
            ["Kullagymnasiet","21,1 %","59,5 %",
             "V.10: 2 580 bestaallda, 1 557 serverade -- 39,7 % overbestaallning"],
            ["Lerbergsskolan","13,7 %","46,0 %","Systematisk overbestaallning hela aret"],
            ["Bruksskolan","11,9 % (viktat)","77,8 %","Oviktat snitt ~17 %, stor varians"],
        ], s, widths=[3.5*cm,3*cm,2.5*cm,7.4*cm]
    ))
    story.append(PageBreak())

    # ── KAP 4: ATER ELEVERNA MATEN ────────────────────────────────────────────
    story.append(chap_header("4","Ater eleverna maten?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Nar svinnet vael uppstar pa tallriken handlar det om beteende vid serveringstillfallet -- "
        "hur maten laggs upp, hur mycket som tas och hur mycket som lamnas kvar.",
        s["body"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(dtbl(
        ["Verksamhetstyp","Serveringssatt","Tallrikssvinn (andel av totalt)","Obs"],
        [
            ["Forskola","Personal portionerar","34 %","Verifierat [8]"],
            ["Grundskola/Gymnasium","Sjalvservering","68 %","Verifierat [8]"],
            ["Aldreomsorg","Personal portionerar","39 %","Verifierat [8]"],
        ], s, widths=[4*cm,4*cm,4.5*cm,3.9*cm]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Portionsvikten skiljer sig ocksa mellan nivan: forskola 275 g, grundskola 400 g, "
        "gymnasium 500 g, aldreomsorg 550 g. Det innebar att samma svinnprocent ger olika "
        "absolut svinn per portion beroende pa verksamhetstyp.",
        s["body"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(box(
        "Vad kan goras?",
        "Serverad forstaportion (eleven far ta mer efterat) ar det enklaste testet. "
        "Det kraver ingen ny utrustning och inga extra kostnader. "
        "Mata svinn 4 veckor fore och 4 veckor efter pa en skola. "
        "Om effekten matchar skillnaden i data ar besparingspotentialen betydande -- "
        "men det maste visas i praktiken forst.",
        s, AMBER_LIGHT
    ))
    story.append(PageBreak())

    # ── KAP 5: SPELAR MENYN ROLL ──────────────────────────────────────────────
    story.append(chap_header("5","Spelar menyn roll?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Genom att koppla daglig svinnregistrering mot matsedeln kan vi se om svinnet "
        "varierar med vad som serveras.",
        s["body"]
    ))
    story.append(chart_menu_waste(mn, fww))
    story.append(Paragraph(
        "Figur 4. Veckor med hogst respektive lagst svinn per portion, kopplat till veckans ratter "
        "(de tre forsta ratternam visas). Kalla: Matsvinn 2025 [1] + Meny skola Utveckling.xlsx [4].",
        s["cap"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Monstret ar konsekvent: veckor med bekanta klassiska ratter (korv stroganoff, "
        "spaghetti, falukorv) har lagst svinn. Veckor med varierade eller ovanliga ratter "
        "har hogst svinn. Skillnaden ar ~90 % mellan basta och samsta vecka.",
        s["body"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(box(
        "Samma monster i forskolan",
        "I forskolornas svinnregistrering (rattnamn ur veckobraden): "
        "Falukorv: 0,008 kg svinn/portion. Pasta med paprikasas: 0,069 kg. "
        "9 ganger sa mycket svinn. Barn och elever ater det de kanner igen.",
        s, BLUE_LIGHT
    ))
    story.append(PageBreak())

    # ── KAP 6: VAD KOSTAR SVINNET ─────────────────────────────────────────────
    story.append(chap_header("6","Vad kostar svinnet?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Inkopsdata anvands har enbart for att satta ekonomiskt varde pa svinnet -- "
        "inte som en fristaaende inkopsrevision. Fragan ar: i vilka varugrupper ar "
        "samma kilo svinn dyrast?",
        s["body"]
    ))
    waste_cost_chart, avg_pct = chart_waste_cost(pur, fww)
    story.append(waste_cost_chart)
    story.append(Paragraph(
        f"Figur 5. Uppskattad svinnkostnad per varugrupp. Antar {avg_pct*100:.1f} % "
        "genomsnittlig svinnprocent (kommunens uppmatta snitt). "
        "Metodvarning: svinnet fordelar sig inte jamt over varugrupper -- detta ar en "
        "proportionerlig uppskattning, inte en exakt matning per vara. "
        "Kalla: Inkop 2025 [2] + Matsvinn 2025 [1].",
        s["cap"]
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(mbox(
        "<b>Varfor ar detta relevant?</b> Om svinnet uppstar i dyra varugrupper som "
        "fisk, kyckling och kott far samma procentuella svinn storre ekonomisk effekt "
        "an om det bestaar av billigare basvaror. Fisk (99-127 kr/kg) ger drygt "
        "6 ganger hogre kostnad per kilo svinn an potatis (16-21 kr/kg). "
        "Det motiverar att prioritera portionsprecision just pa kostsamma ratter.",
        s
    ))
    story.append(Spacer(1,0.3*cm))
    story.append(box(
        "Avtalstrohet som ekonomisk havstang",
        "Utover svinnet: Vasbyhemmet koper 30 % av sina raavaror utanfor upphandlat avtal "
        "(flaggat av kommunens eget system). Vid 2,27 Mkr total inkopskostnad = "
        "indikativt ~680 tkr/ar i avvikelse. Vikhaga 18 % och Nyhamnsgarden 16 % foljer. "
        "Atgardsforslag: gemensam genomgang av inkopslistor med respektive koksansvarig.",
        s, RED_LIGHT
    ))
    story.append(PageBreak())

    # ── KAP 7: REKOMMENDATIONER ────────────────────────────────────────────────
    story.append(chap_header("7","Vad bor testas?",s))
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph(
        "Rekommendationerna baseras pa observerade monster i kommunens egna data. "
        "Kausalitet anges inte dar det inte ar bevisat. Alla atgarder bor testas och maatas.",
        s["body"]
    ))
    story.append(Spacer(1,0.3*cm))

    story.append(rec_box("R1","HOG PRIORITET",
        "Granska inkop utanfor avtal -- borja med Vasbyhemmet",
        "Kommunens eget upphandlingssystem flaggar 30 % av Vasbyhemmets inkop som utanfor avtal. "
        "Gemensam genomgaang av inkopslistor med koksansvarig. Identifiera vilka varor som avviker "
        "och om det finns legitima skal. Notera: 'Retur pantemballage' (38 tkr) bor kontrolleras "
        "separat -- det kan vara en bokforingspost, inte ett reellt livsmedelskop.",
        s, RED))
    story.append(Spacer(1,0.3*cm))

    story.append(rec_box("R2","HOG PRIORITET",
        "Satt mat for bestaallningsprecision -- Kullagymnasiet och Lerbergsskolan",
        "Det indikerar att mat planeras och/eller bestaalls i storre volym an vad som "
        "faktiskt serveras. Kortsiktigt mal: max 10 % overbestaallning. "
        "6-manadersmaal: max 5 %. Infor veckovis aterkopling fran servering till inkopsplanering.",
        s, AMBER))
    story.append(Spacer(1,0.3*cm))

    story.append(rec_box("R3","TESTA OCH MATA",
        "Pilottest: serverad forstaportion i en grundskola",
        "Starkt observerat samband: skolor med sjalvservering har 68 % tallrikssvinn, "
        "mot 34 % i forskolor med personalservering. "
        "Test: Valj en grundskola. Infor serverad forstaportion (eleven far ta mer efterat). "
        "Mata svinn 4 veckor fore och 4 veckor efter. "
        "Bekraftas sambandet -- da ar besparingspotentialen stor. Men testa forst.",
        s, BLUE_MID))
    story.append(Spacer(1,0.3*cm))

    story.append(rec_box("R4","NASTA STEG",
        "Infor daglig svinn- och rattregistrering",
        "Nuvarande registrering sker per vecka. Daglig koppling (ratt + svinn) mojliggor: "
        "vilken ratt, vilken dag, vilken enhet. "
        "Med 6 manaders daglig data kan en prediktion byggas: nasta veckas meny "
        "-- forvanatat svinn -- rekommenderad tillagningsvolym. "
        "Det ar ett operativt planeringsverktyg -- inte en rapport.",
        s, GREEN))
    story.append(PageBreak())

    # ── KALLFORTECKNING ────────────────────────────────────────────────────────
    story.append(Paragraph("Kallforteckning", s["h1"]))
    story.append(HRFlowable(width="100%",thickness=2,color=BLUE_MID,spaceAfter=10))

    story.append(Paragraph("Primaardata (levererad av Hoganas kostverksamhet)", s["h2"]))
    for ref, src, desc in [
        ("[1]","Matsvinn 2025/[enhet].xlsx",
         "21 filer. Dagsnivadata per enhet: bestaallda portioner, serverade portioner, "
         "kokssvinn (kg), serveringssvinn (kg), tallrikssvinn (kg). "
         "Koktyp och portionsvikt extraherade ur metadata. ~4 100 dag-obs. (pipeline-radantal)."),
        ("[2]","Inkop [manad] 2025.xlsx",
         "12 filer, ~23 500 rader. Raavara, varugrupp, leverantor, kg, kr, kr/kg, "
         "andel utanfor avtal (0/100 per rad -- kommunens eget upphandlingssystem)."),
        ("[3]","Data/2025/[enhet]/",
         "19 filer, ~26 000 rader. Portioner per dag, normaliserat fran wide- till long-format."),
        ("[4]","Meny skola/AO Utveckling.xlsx",
         "Matsedel 2025. Varje ratt per dag, skola (50 v.) och aldreomsorg (52 v.)."),
        ("[5]","Utveckling - Naring [...].xlsx",
         "Naringsvarden per ratt. 57 variabler per ratt (energi, protein m.fl.), NNR-bas. "
         "Anvands enbart som databeskrivning -- inga naringsslutsatser dras i denna rapport."),
    ]:
        story.append(Paragraph(f"<b>{ref}</b>   {src}", s["bold"]))
        story.append(Paragraph(desc, s["src"]))
        story.append(Spacer(1,0.1*cm))

    story.append(Spacer(1,0.2*cm))
    story.append(Paragraph("Granskning", s["h2"]))
    story.append(Paragraph(
        "<b>[8]</b>   manus.im (2025). Jamforelse mot Claudes analysunderlag + "
        "Extra kontroll av Claudes paastaaenden. Intern granskning, Konkret Advisory, 2026-06-02. "
        "Verifierar: avtalstrohet, overbestaallning, tallrikssvinnets andel per verksamhetstyp. "
        "Omfattar inte full pipeline-verifiering.", s["src"]
    ))

    story.append(Spacer(1,0.2*cm))
    story.append(Paragraph("Externa kallor", s["h2"]))
    for ref, desc in [
        ("[9]","Livsmedelsverket (2023). Bra mat i skolan. Uppsala."),
        ("[10]","Skollag (SFS 2010:800), 10 kap. 10 SS."),
        ("[11]","Nordiska ministerraadet (2023). Nordic Nutrition Recommendations 2023."),
        ("[12]","Wansink & van Ittersum (2013). Portion size me. J. Exp. Psych.: Applied, 19(4)."),
    ]:
        story.append(Paragraph(f"<b>{ref}</b> {desc}", s["src"]))
        story.append(Spacer(1,0.08*cm))

    story.append(Spacer(1,0.5*cm))
    story.append(HRFlowable(width="100%",thickness=0.5,color=GRAY_MID))
    story.append(Spacer(1,0.2*cm))
    story.append(Paragraph(
        f"Rapport genererad {date.today().strftime('%d %B %Y')}. "
        "Data ags av Hoganas kommun och hanteras konfidentiellt. "
        "Analys: Konkret Advisory. Utvalda fynd granskade: manus.im.",
        s["foot"]
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"\nRapport sparad: {out}")
    return out

if __name__ == "__main__":
    out = build()
    import subprocess
    subprocess.run(["open", str(out)])
