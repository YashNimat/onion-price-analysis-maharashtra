"""Build the Excel 'Sell-Timing What-If' workbook from the forecast outputs.

All calculations are live formulas, so a user can change quantity, transport,
storage cost or spoilage and instantly see the best week to sell.
Usage: python src/build_excel.py   (then open outputs/Mandi_WhatIf.xlsx)
"""
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

from config import PROC_DIR, ROOT

FONT = "Arial"
BLUE = Font(name=FONT, color="0000FF", bold=True)
BASE = Font(name=FONT)
BOLD = Font(name=FONT, bold=True)
HDR = Font(name=FONT, bold=True, color="FFFFFF")
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
GOOD_FILL = PatternFill("solid", fgColor="E2EFDA")
thin = Side(style="thin", color="BFBFBF")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)

# ASSUMPTION: replace with sourced figures (APMC / NHB / ICAR post-harvest loss studies)
SPOILAGE = {"Tomato": 0.05, "Onion": 0.01, "Orange": 0.02, "Soyabean": 0.001,
            "Cotton": 0.001, "Tur(Arhar Fali)": 0.002}


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font, cell.fill = HDR, HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def main():
    fc = pd.read_csv(PROC_DIR / "forecast.csv")
    rec = pd.read_csv(PROC_DIR / "recommendations.csv")
    seas = pd.read_csv(PROC_DIR / "seasonal_index.csv")
    crops = list(rec["commodity"])

    wb = Workbook()

    # ---------------- Guide
    g = wb.active
    g.title = "Guide"
    lines = [
        ("Mandi Price Intelligence - Sell-Timing What-If", BOLD),
        ("", BASE),
        ("How to use", BOLD),
        ("1. Go to the Inputs sheet. Yellow cells with blue text are the cells you can change.", BASE),
        ("2. Pick a commodity, enter your quantity and costs.", BASE),
        ("3. Read the WhatIf sheet: it shows net revenue if you sell now vs after 1-12 weeks.", BASE),
        ("4. If the forecast is flagged unreliable, use Scenario mode (Inputs!B8) and test your own weekly price-change assumptions.", BASE),
        ("", BASE),
        ("Where the numbers come from", BOLD),
        ("Prices: Agmarknet / data.gov.in daily mandi prices, cleaned in Python and stored in SQL.", BASE),
        ("Forecast: best of naive / seasonal-naive / Holt-Winters, chosen by hold-out backtest (see Recommendations).", BASE),
        ("Spoilage rates on Inputs are ASSUMPTIONS - replace them with sourced figures before you publish.", BASE),
        ("Forecasts are estimates with uncertainty, not guarantees. Check the Confidence column on Recommendations.", BASE),
        (f"Latest data week in this workbook: {pd.to_datetime(rec['data_end']).max().date()}. 'Now' means that week, not today.", BASE),
    ]
    if "--demo" in sys.argv:
        lines.insert(0, ("DEMO FILE - BUILT ON SYNTHETIC TEST DATA. NOT REAL PRICES. DO NOT PUBLISH THESE NUMBERS.",
                         Font(name=FONT, bold=True, color="C00000")))
    for i, (t, f) in enumerate(lines, 1):
        g.cell(row=i, column=1, value=t).font = f
    g.column_dimensions["A"].width = 110

    # ---------------- Inputs
    inp = wb.create_sheet("Inputs")
    inp["A1"], inp["A1"].font = "Inputs", BOLD
    rows = [
        ("Commodity", crops[0], "Pick from list"),
        ("Quantity (quintals)", 100, "Example value - replace with yours"),
        ("Transport cost (Rs per quintal)", 60, "Assumption - replace with your actual cost"),
        ("Storage cost (Rs per quintal per week)", 8, "Assumption - replace with your actual cost"),
    ]
    for i, (label, val, note) in enumerate(rows, start=3):
        inp.cell(row=i, column=1, value=label).font = BASE
        c = inp.cell(row=i, column=2, value=val)
        c.font, c.fill, c.border = BLUE, INPUT_FILL, BOX
        inp.cell(row=i, column=3, value=note).font = Font(name=FONT, italic=True, color="7F7F7F")
    dv = DataValidation(type="list", formula1="=$A$12:$A$%d" % (11 + len(crops)), allow_blank=False)
    inp.add_data_validation(dv); dv.add("B3")

    inp["A7"], inp["B7"] = "Spoilage / quality loss per week (selected commodity)", "=INDEX($B$12:$B$%d,MATCH($B$3,$A$12:$A$%d,0))" % (11 + len(crops), 11 + len(crops))
    inp["A7"].font = BASE; inp["B7"].font = BASE; inp["B7"].number_format = "0.0%"
    inp["C7"] = "Looked up from the table below"
    inp["C7"].font = Font(name=FONT, italic=True, color="7F7F7F")

    low_conf = str(rec["confidence"].iloc[0]).startswith("Low")
    inp["A8"], inp["B8"] = "Price source for weeks 1-12", "Scenario" if low_conf else "Model forecast"
    inp["A9"], inp["B9"] = "Scenario: expected price change per week", 0.0
    for a in ("B8", "B9"):
        inp[a].font, inp[a].fill, inp[a].border = BLUE, INPUT_FILL, BOX
    inp["B9"].number_format = "0.0%"
    inp["C8"] = "Pick 'Model forecast' or 'Scenario'. Scenario is the safe default when the forecast is unreliable."
    inp["C9"] = "Used only in Scenario mode, e.g. 2% = price rises 2% every week. Try -2%, 0%, 2%, 4%."
    for a in ("C8", "C9"):
        inp[a].font = Font(name=FONT, italic=True, color="7F7F7F")
    dv2 = DataValidation(type="list", formula1='"Model forecast,Scenario"', allow_blank=False)
    inp.add_data_validation(dv2); dv2.add("B8")

    inp["A10"] = "Spoilage assumptions by commodity (ASSUMPTION - replace with sourced figures)"
    inp["A10"].font = BOLD
    inp["A11"], inp["B11"] = "Commodity", "Loss per week"
    style_header(inp, 11, 2)
    for i, crop in enumerate(crops, start=12):
        inp.cell(row=i, column=1, value=crop).font = BASE
        c = inp.cell(row=i, column=2, value=SPOILAGE.get(crop, 0.01))
        c.font, c.fill, c.border, c.number_format = BLUE, INPUT_FILL, BOX, "0.0%"
    inp.column_dimensions["A"].width = 50; inp.column_dimensions["B"].width = 18; inp.column_dimensions["C"].width = 48

    # ---------------- Forecast (data)
    f = wb.create_sheet("Forecast")
    heads = ["commodity", "week_start", "forecast_price", "lower_80", "upper_80", "model", "week_no", "key"]
    for j, h in enumerate(heads, 1):
        f.cell(row=1, column=j, value=h)
    style_header(f, 1, len(heads))
    for i, r in enumerate(fc.itertuples(index=False), start=2):
        f.cell(row=i, column=1, value=r.commodity)
        f.cell(row=i, column=2, value=pd.to_datetime(r.week_start).date()).number_format = "dd-mmm-yy"
        for j, v in enumerate([r.forecast, r.lower_80, r.upper_80], start=3):
            f.cell(row=i, column=j, value=round(float(v), 0)).number_format = "#,##0"
        f.cell(row=i, column=6, value=r.model)
        f.cell(row=i, column=7, value=f"=COUNTIF($A$2:A{i},A{i})")
        f.cell(row=i, column=8, value=f'=A{i}&"|"&G{i}')
    nlast = len(fc) + 1
    for col, w in zip("ABCDEFGH", [18, 12, 15, 12, 12, 40, 9, 22]):
        f.column_dimensions[col].width = w
    f.cell(row=nlast + 2, column=1, value="Source: src/forecast.py output (data/processed/forecast.csv). Prices in Rs per quintal.").font = Font(name=FONT, italic=True)

    # ---------------- Recommendations (data)
    rs = wb.create_sheet("Recommendations")
    rh = ["Commodity", "Current price (4-wk avg)", "Best week in horizon", "Expected price", "Uplift %",
          "Model", "Backtest MAPE %", "Naive MAPE %", "Improvement vs naive %", "Confidence", "Action"]
    for j, h in enumerate(rh, 1):
        rs.cell(row=1, column=j, value=h)
    style_header(rs, 1, len(rh))
    for i, r in enumerate(rec.itertuples(index=False), start=2):
        vals = [r.commodity, r.current_price, pd.to_datetime(r.best_week).date(), r.expected_price,
                r.uplift_pct, r.model, r.backtest_mape_pct, r.naive_mape_pct,
                r.improvement_vs_naive_pct, r.confidence, r.action]
        for j, v in enumerate(vals, 1):
            c = rs.cell(row=i, column=j, value=round(v, 1) if isinstance(v, float) else v)
            c.font = BASE
            if j in (2, 4): c.number_format = "#,##0"
            if j == 3: c.number_format = "dd-mmm-yy"
    for col, w in zip("ABCDEFGHIJK", [18, 16, 16, 14, 10, 40, 14, 12, 18, 12, 26]):
        rs.column_dimensions[col].width = w
    rs.row_dimensions[1].height = 32

    # ---------------- Seasonality (data)
    se = wb.create_sheet("Seasonality")
    piv = seas.pivot(index="month_no", columns="commodity", values="seasonal_index").reindex(columns=crops)
    se.cell(row=1, column=1, value="Month")
    for j, crop in enumerate(crops, 2):
        se.cell(row=1, column=j, value=crop)
    style_header(se, 1, len(crops) + 1)
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, m in enumerate(piv.index, start=2):
        se.cell(row=i, column=1, value=names[m - 1]).font = BASE
        for j, crop in enumerate(crops, 2):
            c = se.cell(row=i, column=j, value=round(float(piv.loc[m, crop]), 3))
            c.number_format = "0.000"; c.font = BASE
    se.cell(row=15, column=1, value="Index > 1.00 means the month is priced above that commodity's yearly average.").font = Font(name=FONT, italic=True)
    se.column_dimensions["A"].width = 10
    for j in range(2, len(crops) + 2):
        se.column_dimensions[se.cell(row=1, column=j).column_letter].width = 16
    lc = LineChart(); lc.title = "Seasonal price index by month"; lc.height, lc.width = 8, 18
    lc.add_data(Reference(se, min_col=2, max_col=len(crops) + 1, min_row=1, max_row=13), titles_from_data=True)
    lc.set_categories(Reference(se, min_col=1, min_row=2, max_row=13))
    se.add_chart(lc, "J2")

    # ---------------- WhatIf (calculations)
    w = wb.create_sheet("WhatIf")
    w["A1"] = "Sell-timing what-if"; w["A1"].font = BOLD
    w["A2"] = "Commodity"; w["B2"] = "=Inputs!B3"
    w["A3"] = "Best week to sell (0 = now)"; w["B3"] = "=MATCH(MAX(H8:H20),H8:H20,0)-1"
    w["C3"] = "Net revenue at best week (Rs)"; w["D3"] = "=MAX(H8:H20)"
    w["A4"] = "Gain vs selling now (Rs)"; w["B4"] = "=D3-H8"
    w["C4"] = "Decision"; w["D4"] = '=IF(B4>0,"Hold "&B3&" week(s)","Sell now")'
    w["A5"] = "Forecast confidence"; w["A5"].font = BOLD
    w["B5"] = "=IFERROR(INDEX(Recommendations!$J$2:$J$%d,MATCH($B$2,Recommendations!$A$2:$A$%d,0)),\"\")" % (1 + len(crops), 1 + len(crops))
    w["B5"].font = BASE; w["B5"].fill = GOOD_FILL
    w["C5"] = '=IF(Inputs!$B$8="Scenario","Mode: SCENARIO (your assumed weekly price change)",IF(LEFT(B5,3)="Low","WARNING: forecast is unreliable. Switch Inputs!B8 to Scenario.","Mode: model forecast"))'
    w["C5"].font = Font(name=FONT, bold=True, color="C00000")
    for a in ["A2", "A3", "A4", "C3", "C4"]:
        w[a].font = BOLD
    for a in ["B2", "B3", "B4", "D3", "D4"]:
        w[a].font = BASE; w[a].fill = GOOD_FILL
    w["D3"].number_format = "#,##0"; w["B4"].number_format = "#,##0"

    wh = ["Week", "Week start", "Expected price (Rs/qtl)", "Quality factor", "Gross revenue (Rs)",
          "Storage cost (Rs)", "Transport cost (Rs)", "Net revenue (Rs)", "Gain vs sell now (Rs)"]
    for j, h in enumerate(wh, 1):
        w.cell(row=7, column=j, value=h)
    style_header(w, 7, len(wh)); w.row_dimensions[7].height = 32
    last_fc_row = nlast
    for k in range(0, 13):
        r = 8 + k
        w.cell(row=r, column=1, value=k)
        if k == 0:
            w.cell(row=r, column=2, value="Now")
            w.cell(row=r, column=3, value="=INDEX(Recommendations!$B$2:$B$%d,MATCH($B$2,Recommendations!$A$2:$A$%d,0))" % (1 + len(crops), 1 + len(crops)))
        else:
            w.cell(row=r, column=2, value=f'=IFERROR(INDEX(Forecast!$B$2:$B${last_fc_row},MATCH($B$2&"|"&A{r},Forecast!$H$2:$H${last_fc_row},0)),"")').number_format = "dd-mmm-yy"
            w.cell(row=r, column=3, value=f'=IF(Inputs!$B$8="Scenario",C{r-1}*(1+Inputs!$B$9),IFERROR(INDEX(Forecast!$C$2:$C${last_fc_row},MATCH($B$2&"|"&A{r},Forecast!$H$2:$H${last_fc_row},0)),C{r-1}))')
        w.cell(row=r, column=4, value=f"=(1-Inputs!$B$7)^A{r}").number_format = "0.000"
        w.cell(row=r, column=5, value=f"=C{r}*Inputs!$B$4*D{r}")
        w.cell(row=r, column=6, value=f"=Inputs!$B$6*Inputs!$B$4*A{r}")
        w.cell(row=r, column=7, value="=Inputs!$B$5*Inputs!$B$4")
        w.cell(row=r, column=8, value=f"=E{r}-F{r}-G{r}")
        w.cell(row=r, column=9, value=f"=H{r}-$H$8")
        for col in (3, 5, 6, 7, 8, 9):
            w.cell(row=r, column=col).number_format = "#,##0"
        for col in range(1, 10):
            w.cell(row=r, column=col).font = BASE
    for col, wd in zip("ABCDEFGHI", [26, 14, 20, 14, 20, 16, 18, 18, 20]):
        w.column_dimensions[col].width = wd
    w.cell(row=22, column=1, value="Assumptions: forecast prices from Forecast sheet; quality loss compounds weekly; costs from Inputs sheet.").font = Font(name=FONT, italic=True)
    ch = LineChart(); ch.title = "Net revenue by selling week"; ch.height, ch.width = 8, 18
    ch.add_data(Reference(w, min_col=8, min_row=7, max_row=20), titles_from_data=True)
    ch.set_categories(Reference(w, min_col=1, min_row=8, max_row=20))
    ch.y_axis.title = "Rs"; ch.x_axis.title = "Weeks from now"
    w.add_chart(ch, "K2")

    out = ROOT / "outputs"; out.mkdir(exist_ok=True)
    fname = "DEMO_synthetic_Mandi_WhatIf.xlsx" if "--demo" in sys.argv else "Mandi_WhatIf.xlsx"
    wb.save(out / fname)
    print("saved", out / fname)


if __name__ == "__main__":
    main()
