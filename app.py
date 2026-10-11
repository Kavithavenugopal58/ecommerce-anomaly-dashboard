
# ================================================================
# FINAL E-COMMERCE ANOMALY DASHBOARD + HTML EXPORT
# Requires: detected, alert_summary, product_df
# Optional: configured Gemini client named `client`
# ================================================================

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output
from google.colab import files
import html
import json

# -------------------- 1. PREPARE DATA ----------------------------

for name in ["detected", "alert_summary", "product_df"]:
    if name not in globals():
        raise NameError(
            f"`{name}` is missing. Run your existing data-preparation cells first."
        )

det = detected.copy()
alerts = alert_summary.copy()
prod = product_df.copy()

for df in [det, alerts, prod]:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

det = det.dropna(subset=["Date"]).sort_values("Date")
alerts = alerts.dropna(subset=["Date"]).sort_values("Date")
prod = prod.dropna(subset=["Date"]).sort_values("Date")

# Priority and maximum deviation
severity_col = "Overall_Anomaly_Severity"

priority_map = {
    "critical": "P1 - Immediate",
    "high": "P2 - High",
    "watch": "P3 - Watch",
    "normal": "P4 - Normal"
}

alerts["Alert_Priority"] = (
    alerts.get("Alert_Priority", pd.Series(index=alerts.index, dtype="object"))
    .replace(r"^\s*$", np.nan, regex=True)
    .fillna(
        alerts[severity_col].astype(str).str.lower().map(priority_map)
    )
    .fillna("P3 - Watch")
)

dev_cols = [
    "Total_Orders_Deviation_Pct",
    "Total_Revenue_INR_Deviation_Pct",
    "Weighted_AOV_INR_Deviation_Pct",
    "Avg_Cancellation_Rate_Pct_Deviation_Pct"
]
dev_cols = [c for c in dev_cols if c in alerts.columns]

if dev_cols:
    calculated_max = (
        alerts[dev_cols].apply(pd.to_numeric, errors="coerce")
        .abs().max(axis=1)
    )
    if "Max_Absolute_Deviation_Pct" not in alerts.columns:
        alerts["Max_Absolute_Deviation_Pct"] = calculated_max
    else:
        alerts["Max_Absolute_Deviation_Pct"] = (
            pd.to_numeric(
                alerts["Max_Absolute_Deviation_Pct"], errors="coerce"
            ).fillna(calculated_max)
        )

KPI = {
    "Orders": {
        "actual": "Total_Orders",
        "expected": "Total_Orders_Expected",
        "dev": "Total_Orders_Deviation_Pct",
        "flag": "Orders_Is_Anomaly",
        "product": "Orders",
        "fmt": "number"
    },
    "Revenue": {
        "actual": "Total_Revenue_INR",
        "expected": "Total_Revenue_INR_Expected",
        "dev": "Total_Revenue_INR_Deviation_Pct",
        "flag": "Revenue_Is_Anomaly",
        "product": "Revenue_INR",
        "fmt": "currency"
    },
    "AOV": {
        "actual": "Weighted_AOV_INR",
        "expected": "Weighted_AOV_INR_Expected",
        "dev": "Weighted_AOV_INR_Deviation_Pct",
        "flag": "AOV_Is_Anomaly",
        "product": "AOV_INR",
        "fmt": "currency"
    },
    "Cancellation Rate": {
        "actual": "Avg_Cancellation_Rate_Pct",
        "expected": "Avg_Cancellation_Rate_Pct_Expected",
        "dev": "Avg_Cancellation_Rate_Pct_Deviation_Pct",
        "flag": "Cancellation_Rate_Is_Anomaly",
        "product": "Cancellation_Rate_Pct",
        "fmt": "percent"
    }
}

def find_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

owner_col = find_col(alerts, ["Owner"])
support_col = find_col(alerts, ["Supporting_Owner", "Supporting Owner"])
kpi_count_col = find_col(alerts, ["Affected_KPI_Count", "KPI_Count"])
root_col = find_col(
    alerts, ["Root_Cause_Hypothesis", "Probable_Root_Cause", "Root_Cause"]
)
action_col = find_col(alerts, ["Recommended_Action", "Action"])
confidence_col = find_col(alerts, ["Root_Cause_Confidence", "Confidence"])
narrative_col = find_col(
    alerts, ["LLM_Alert_Narrative", "Alert_Narrative", "LLM_Narrative"]
)

def fmt(value, kind):
    if pd.isna(value):
        return "—"
    if kind == "currency":
        return f"₹{value:,.0f}"
    if kind == "percent":
        return f"{value:.1f}%"
    return f"{value:,.0f}"

def safe_text(value):
    return html.escape(str(value)) if pd.notna(value) else "—"

# -------------------- 2. FILTERS --------------------------------

min_date = det["Date"].min().date()
max_date = det["Date"].max().date()

start_w = widgets.DatePicker(description="From", value=min_date)
end_w = widgets.DatePicker(description="To", value=max_date)

kpi_w = widgets.Dropdown(
    options=list(KPI.keys()), value="Orders", description="Trend KPI:"
)

geo_w = widgets.Dropdown(
    options=["All"] + (
        sorted(prod["Geography"].dropna().astype(str).unique())
        if "Geography" in prod.columns else []
    ),
    description="Geography:"
)

cat_w = widgets.Dropdown(
    options=["All"] + (
        sorted(prod["Category"].dropna().astype(str).unique())
        if "Category" in prod.columns else []
    ),
    description="Category:"
)

priority_w = widgets.Dropdown(
    options=["All", "P1 - Immediate", "P2 - High", "P3 - Watch"],
    value="All", description="Priority:"
)

date_w = widgets.Dropdown(options=[], description="Investigate date:")

refresh_btn = widgets.Button(
    description="Refresh dashboard", button_style="primary", icon="refresh"
)
export_btn = widgets.Button(
    description="Export Dashboard HTML", button_style="success", icon="download"
)
narrative_btn = widgets.Button(
    description="Generate Gemini Narrative", button_style="info", icon="comment"
)

dashboard_out = widgets.Output()
message_out = widgets.Output()

narrative_state = {"date": None, "text": None, "source": None}

# -------------------- 3. HTML HELPERS ----------------------------

def make_card(title, value, subtitle, colour):
    return f"""
    <div class="kpi" style="border-top:4px solid {colour}">
      <div class="kpi-label">{title}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{subtitle}</div>
    </div>
    """

def dashboard_css():
    return """
    <style>
    .dash{font-family:Arial,sans-serif;background:#eef4fb;color:#102a56;padding:10px;border-radius:12px}
    .hero{background:linear-gradient(105deg,#123b79,#247fa4);color:white;padding:20px;border-radius:13px;margin-bottom:12px}
    .hero h1{margin:0;color:white;font-size:27px}.hero p{margin:6px 0 0;color:#eef7ff;font-size:13px}
    .cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0}
    .kpi{background:white;border:1px solid #d8e4f2;border-radius:12px;padding:14px;min-height:92px}
    .kpi-label{font-size:13px;color:#53657e;font-weight:bold}
    .kpi-value{font-size:25px;font-weight:800;margin:7px 0;color:#102a56}
    .kpi-sub{font-size:10px;color:#66758b}
    .panel{background:white;border:1px solid #d8e4f2;border-radius:12px;padding:12px;margin-bottom:10px;min-width:0}
    .title{font-size:17px;font-weight:800;margin-bottom:8px}
    .row2{display:grid;grid-template-columns:2fr 1fr;gap:10px}
    .row3{display:grid;grid-template-columns:1fr 1.2fr;gap:10px}
    table.feed{width:100%;border-collapse:collapse;font-size:12px;background:white}
    table.feed th{background:#edf2f7;text-align:left;padding:9px;border-bottom:1px solid #d8e4f2}
    table.feed td{padding:8px;border-bottom:1px solid #d9dfe7}
    .critical{color:#c62828;font-weight:bold}
    .high{color:#e87500;font-weight:bold}
    .watch{color:#9a7800;font-weight:bold}
    @media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}.row2,.row3{grid-template-columns:1fr}}
    </style>
    """

def get_filtered_data():
    start = pd.Timestamp(start_w.value or min_date)
    end = pd.Timestamp(end_w.value or max_date)
    if start > end:
        start, end = end, start

    d = det[(det.Date >= start) & (det.Date <= end)].copy()
    a = alerts[(alerts.Date >= start) & (alerts.Date <= end)].copy()
    p = prod[(prod.Date >= start) & (prod.Date <= end)].copy()

    if geo_w.value != "All" and "Geography" in p.columns:
        p = p[p["Geography"].astype(str) == geo_w.value]
    if cat_w.value != "All" and "Category" in p.columns:
        p = p[p["Category"].astype(str) == cat_w.value]
    if priority_w.value != "All":
        a = a[a["Alert_Priority"].astype(str) == priority_w.value]

    return start, end, d, a, p

# -------------------- 4. RENDER DASHBOARD ------------------------

def render_dashboard(_=None):
    start, end, d, a, p = get_filtered_data()

    dates = sorted(a.Date.dt.strftime("%Y-%m-%d").unique().tolist())
    if not dates:
        dates = sorted(d.Date.dt.strftime("%Y-%m-%d").unique().tolist())

    previous = date_w.value
    date_w.options = dates
    if previous in dates:
        date_w.value = previous
    elif dates:
        date_w.value = dates[-1]

    with dashboard_out:
        clear_output(wait=True)

        if d.empty:
            display(HTML("<b>No data for the selected date range.</b>"))
            return

        latest = d.sort_values("Date").iloc[-1]
        cards = []

        card_specs = [
            ("Total Orders", "Total_Orders", "Orders", "#2f80ed"),
            ("Total Revenue", "Total_Revenue_INR", "Revenue", "#1c9a70"),
            ("Average Order Value (AOV)", "Weighted_AOV_INR", "AOV", "#e8752d"),
            ("Cancellation Rate", "Avg_Cancellation_Rate_Pct", "Cancellation Rate", "#8b5bd6")
        ]

        for title, col, kname, colour in card_specs:
            cfg = KPI[kname]
            value = latest.get(col, np.nan)
            expected = latest.get(cfg["expected"], np.nan)
            deviation = latest.get(cfg["dev"], np.nan)
            subtitle = f"Latest: {latest.Date:%d %b %Y}"
            if pd.notna(expected):
                subtitle += f" • Expected {fmt(expected, cfg['fmt'])}"
            if pd.notna(deviation):
                subtitle += f" • Deviation {deviation:+.1f}%"
            cards.append(make_card(title, fmt(value, cfg["fmt"]), subtitle, colour))

        display(HTML(dashboard_css() + f"""
        <div class="dash">
          <div class="hero">
            <h1>🛒 E-Commerce Anomaly Monitoring Dashboard</h1>
            <p>AI-assisted detection • KPI monitoring • Evidence-led investigation • Action ownership</p>
            <p>{start:%d %b %Y} – {end:%d %b %Y}</p>
          </div>
          <div class="cards">{''.join(cards)}</div>
        """))

        # Trend chart changes with the KPI dropdown
        cfg = KPI[kpi_w.value]
        trend = go.Figure()
        trend.add_trace(go.Scatter(
            x=d.Date, y=d[cfg["actual"]], mode="lines",
            name=f"Actual {kpi_w.value}", line=dict(color="#1769e0", width=2.5)
        ))
        if cfg["expected"] in d.columns:
            trend.add_trace(go.Scatter(
                x=d.Date, y=d[cfg["expected"]], mode="lines",
                name="Expected baseline",
                line=dict(color="#8da0b8", dash="dash")
            ))
        if cfg["flag"] in d.columns:
            anomaly_rows = d[d[cfg["flag"]].fillna(False).astype(bool)]
            if not anomaly_rows.empty:
                trend.add_trace(go.Scatter(
                    x=anomaly_rows.Date, y=anomaly_rows[cfg["actual"]],
                    mode="markers", name="Anomaly",
                    marker=dict(color="red", size=9)
                ))
        trend.update_layout(
            title=f"{kpi_w.value} Trend with Anomalies",
            height=330, template="plotly_white",
            margin=dict(l=10, r=10, t=45, b=10),
            legend=dict(orientation="h", y=1.12),
            hovermode="x unified"
        )
        trend_html = trend.to_html(full_html=False, include_plotlyjs="cdn")

        # Priority donut
        severity_counts = (
            a[severity_col].astype(str).str.title().value_counts()
            if not a.empty else pd.Series(dtype=int)
        )
        labels = ["Critical", "High", "Watch"]
        values = [int(severity_counts.get(x, 0)) for x in labels]
        priority_fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=.62,
            marker_colors=["#f04438", "#ff8a00", "#f4c430"],
            textinfo="label+value"
        ))
        priority_fig.update_layout(
            title="Alerts by Priority", height=330,
            template="plotly_white", margin=dict(l=5, r=5, t=45, b=5),
            annotations=[dict(
                text=f"{sum(values)}<br>Alerts", x=.5, y=.5,
                showarrow=False, font_size=17
            )]
        )
        priority_html = priority_fig.to_html(
            full_html=False, include_plotlyjs=False
        )

        display(HTML(
            '<div class="row2"><div class="panel">' + trend_html +
            '</div><div class="panel">' + priority_html + '</div></div>'
        ))

        # Category and product investigation charts
        selected_date = date_w.value
        if selected_date:
            target = pd.Timestamp(selected_date)
            pday = p[p.Date == target].copy()
            if pday.empty:
                pday = prod[prod.Date == target].copy()

            metric = cfg["product"]
            category_html = "<p>No category data available.</p>"
            product_html = "<p>No product data available.</p>"

            if not pday.empty and "Category" in pday.columns and metric in pday.columns:
                category_data = pday.groupby("Category", as_index=False)[metric].sum()
                cf = px.pie(
                    category_data, names="Category", values=metric, hole=.38,
                    title=f"{kpi_w.value} by Category • {selected_date}"
                )
                cf.update_layout(height=300, template="plotly_white")
                category_html = cf.to_html(
                    full_html=False, include_plotlyjs=False
                )

            if not pday.empty and "Product_Name" in pday.columns and metric in pday.columns:
                product_data = (
                    pday.groupby("Product_Name", as_index=False)[metric]
                    .sum().sort_values(metric, ascending=False).head(10)
                )
                pf = px.bar(
                    product_data, x=metric, y="Product_Name",
                    orientation="h",
                    title=f"Top Products by {kpi_w.value} • {selected_date}"
                )
                pf.update_layout(
                    height=300, template="plotly_white",
                    yaxis=dict(autorange="reversed")
                )
                product_html = pf.to_html(
                    full_html=False, include_plotlyjs=False
                )

            display(HTML(
                '<div class="row3"><div class="panel"><div class="title">Category Investigation</div>' +
                category_html +
                '</div><div class="panel"><div class="title">Product Investigation</div>' +
                product_html +
                '</div></div><p style="font-size:11px;color:#66758b">'
                'These charts show selected-KPI contribution on the selected date, '
                'not proof of causation.</p>'
            ))

        # Actionable Alert Feed
        if not a.empty:
            feed = a.copy()
            feed["_severity_rank"] = (
                feed[severity_col].astype(str).str.lower()
                .map({"critical": 0, "high": 1, "watch": 2, "normal": 3})
                .fillna(4)
            )
            feed["_dev_rank"] = pd.to_numeric(
                feed.get("Max_Absolute_Deviation_Pct", 0),
                errors="coerce"
            ).abs()
            feed = feed.sort_values(
                ["_severity_rank", "_dev_rank"], ascending=[True, False]
            ).head(10).copy()
            feed.insert(0, "Rank", range(1, len(feed) + 1))

            def get_values(col, default="—"):
                if col and col in feed.columns:
                    return feed[col]
                return pd.Series([default] * len(feed), index=feed.index)

            shown = pd.DataFrame({
                "Rank": feed["Rank"],
                "Date": feed.Date.dt.strftime("%d-%b-%Y"),
                "Severity": get_values(severity_col),
                "KPI Count": get_values(kpi_count_col),
                "Max Deviation %": pd.to_numeric(
                    get_values("Max_Absolute_Deviation_Pct"), errors="coerce"
                ).map(lambda x: f"{x:.2f}%" if pd.notna(x) else "—"),
                "Priority": get_values("Alert_Priority"),
                "Owner": get_values(owner_col),
                "Supporting Owner": get_values(support_col)
            })
            feed_html = shown.to_html(
                index=False, escape=True, classes="feed"
            )
        else:
            feed_html = "<p>No alerts match the selected filters.</p>"

        display(HTML(f"""
        <div class="panel">
          <div class="title">Actionable Alert Feed</div>
          <p>10 highest-priority anomalies requiring attention.</p>
          {feed_html}
        </div>
        """))

        # Narrative panel
        narrative = "No saved LLM narrative. Select an alert date and click Generate Gemini Narrative."
        row = alerts[alerts.Date == pd.Timestamp(selected_date)] if selected_date else pd.DataFrame()

        if not row.empty:
            r = row.iloc[-1]
            if narrative_state["date"] == selected_date and narrative_state["text"]:
                narrative = narrative_state["text"]
            elif narrative_col and pd.notna(r.get(narrative_col)):
                narrative = str(r[narrative_col])

            day = det[det.Date == pd.Timestamp(selected_date)]
            evidence = []
            if not day.empty:
                dr = day.iloc[0]
                for label, c in KPI.items():
                    actual = dr.get(c["actual"], np.nan)
                    expected = dr.get(c["expected"], np.nan)
                    deviation = dr.get(c["dev"], np.nan)
                    if pd.notna(actual) and pd.notna(expected):
                        evidence.append(
                            f"{label}: actual {fmt(actual,c['fmt'])}; expected "
                            f"{fmt(expected,c['fmt'])}; deviation "
                            f"{deviation:+.2f}%"
                            if pd.notna(deviation) else
                            f"{label}: actual {fmt(actual,c['fmt'])}; expected {fmt(expected,c['fmt'])}"
                        )

            display(HTML(f"""
            <div class="panel">
              <div class="title">Alert Narrative & Investigation • {selected_date}</div>
              <p><b>Severity:</b> {safe_text(r.get(severity_col,'Unknown'))}</p>
              <p><b>Issue:</b> Statistical monitoring flagged unusual movement in one or more KPIs.</p>
              <b>Business impact / evidence</b>
              <ul>{''.join('<li>'+safe_text(x)+'</li>' for x in evidence)}</ul>
              <p><b>Probable root-cause hypothesis:</b> {safe_text(r.get(root_col,'Not available') if root_col else 'Not available')}</p>
              <p><b>Confidence:</b> {safe_text(r.get(confidence_col,'Not assessed') if confidence_col else 'Not assessed')}</p>
              <p><b>Owner:</b> {safe_text(r.get(owner_col,'Unassigned') if owner_col else 'Unassigned')}</p>
              <p><b>Supporting Owner:</b> {safe_text(r.get(support_col,'Unassigned') if support_col else 'Unassigned')}</p>
              <p><b>Recommended Action:</b> {safe_text(r.get(action_col,'Review affected KPIs and segment evidence.') if action_col else 'Review affected KPIs and segment evidence.')}</p>
              <hr><b>LLM Narrative</b><pre style="white-space:pre-wrap;font-family:Arial,sans-serif">{safe_text(narrative)}</pre>
              <p style="font-size:11px;color:#66758b">Root-cause statements are hypotheses, not confirmed causes.</p>
            </div></div>
            """))

# -------------------- 5. GEMINI NARRATIVE ------------------------

def generate_narrative(_):
    with message_out:
        clear_output(wait=True)
        selected = date_w.value

        if not selected:
            print("Please select an investigation date.")
            return

        rows = alerts[alerts.Date == pd.Timestamp(selected)]
        if rows.empty:
            print("No alert found for the selected date.")
            return

        r = rows.iloc[-1]
        day = det[det.Date == pd.Timestamp(selected)]
        evidence = {}

        if not day.empty:
            dr = day.iloc[0]
            for label, c in KPI.items():
                evidence[label] = {
                    "actual": dr.get(c["actual"], None),
                    "expected": dr.get(c["expected"], None),
                    "deviation_pct": dr.get(c["dev"], None)
                }

        context = {
            "date": selected,
            "severity": str(r.get(severity_col, "Unknown")),
            "priority": str(r.get("Alert_Priority", "Unknown")),
            "owner": str(r.get(owner_col, "Unassigned")) if owner_col else "Unassigned",
            "supporting_owner": str(r.get(support_col, "Unassigned")) if support_col else "Unassigned",
            "root_cause_hypothesis": str(r.get(root_col, "Not available")) if root_col else "Not available",
            "recommended_action": str(r.get(action_col, "Not available")) if action_col else "Not available",
            "kpi_evidence": evidence
        }

        prompt = (
            "Write a business-friendly e-commerce anomaly alert narrative using only "
            "the supplied incident data. Do not invent facts or claim the cause is confirmed. "
            "Use headings: ALERT TITLE, ISSUE, BUSINESS IMPACT, PROBABLE ROOT-CAUSE "
            "HYPOTHESIS, EVIDENCE, CONFIDENCE AND LIMITATIONS, OWNER, SUPPORTING OWNER, "
            "RECOMMENDED ACTION. Data: " + json.dumps(context, default=str)
        )

        try:
            if "client" not in globals():
                raise RuntimeError("Gemini client `client` is not configured.")

            response = client.interactions.create(
                model=globals().get("GEMINI_MODEL", "gemini-3.8-flash"),
                input=prompt
            )
            narrative = getattr(response, "output_text", None)

            if not narrative:
                raise RuntimeError("Gemini returned an empty response.")

            narrative_state.update({
                "date": selected, "text": narrative, "source": "Gemini"
            })

            if narrative_col is None:
                alerts["LLM_Alert_Narrative"] = None
                narrative_col = "LLM_Alert_Narrative"

            alerts.loc[
                alerts.Date == pd.Timestamp(selected), narrative_col
            ] = narrative

            print("Gemini narrative generated successfully.")
            render_dashboard()

        except Exception as e:
            fallback = (
                f"ALERT TITLE: {selected} — {r.get(severity_col,'Unknown')} anomaly\n"
                "ISSUE: Statistical monitoring detected unusual KPI movement.\n"
                f"PROBABLE ROOT-CAUSE HYPOTHESIS: "
                f"{r.get(root_col,'Investigate KPI and segment evidence') if root_col else 'Investigate KPI and segment evidence'}\n"
                f"OWNER: {r.get(owner_col,'Unassigned') if owner_col else 'Unassigned'}\n"
                f"SUPPORTING OWNER: {r.get(support_col,'Unassigned') if support_col else 'Unassigned'}\n"
                f"RECOMMENDED ACTION: {r.get(action_col,'Review KPI and segment evidence') if action_col else 'Review KPI and segment evidence'}\n"
                "LIMITATION: Root cause is a hypothesis and must be validated."
            )
            narrative_state.update({
                "date": selected, "text": fallback,
                "source": "Rule-based fallback"
            })
            print("Gemini request failed:", e)
            print("Showing a rule-based fallback, not an LLM-generated narrative.")
            render_dashboard()

# -------------------- 6. EXPORT CURRENT VIEW TO HTML ------------

def export_dashboard(_):
    with message_out:
        clear_output(wait=True)

        start, end, d, a, p = get_filtered_data()
        if d.empty:
            print("No data available to export.")
            return

        cfg = KPI[kpi_w.value]
        latest = d.sort_values("Date").iloc[-1]
        cards = []

        for title, col, kname, colour in [
            ("Total Orders","Total_Orders","Orders","#2f80ed"),
            ("Total Revenue","Total_Revenue_INR","Revenue","#1c9a70"),
            ("Average Order Value","Weighted_AOV_INR","AOV","#e8752d"),
            ("Cancellation Rate","Avg_Cancellation_Rate_Pct","Cancellation Rate","#8b5bd6")
        ]:
            c = KPI[kname]
            value = latest.get(col, np.nan)
            expected = latest.get(c["expected"], np.nan)
            deviation = latest.get(c["dev"], np.nan)
            subtitle = f"Latest: {latest.Date:%d %b %Y}"
            if pd.notna(expected):
                subtitle += f" • Expected {fmt(expected,c['fmt'])}"
            if pd.notna(deviation):
                subtitle += f" • Deviation {deviation:+.1f}%"
            cards.append(make_card(title, fmt(value,c["fmt"]), subtitle, colour))

        trend = go.Figure()
        trend.add_trace(go.Scatter(
            x=d.Date, y=d[cfg["actual"]], mode="lines",
            name=f"Actual {kpi_w.value}", line=dict(color="#1769e0",width=2.5)
        ))
        if cfg["expected"] in d:
            trend.add_trace(go.Scatter(
                x=d.Date, y=d[cfg["expected"]], mode="lines",
                name="Expected baseline", line=dict(color="#8da0b8",dash="dash")
            ))
        if cfg["flag"] in d:
            anomaly_rows = d[d[cfg["flag"]].fillna(False).astype(bool)]
            if not anomaly_rows.empty:
                trend.add_trace(go.Scatter(
                    x=anomaly_rows.Date, y=anomaly_rows[cfg["actual"]],
                    mode="markers", name="Anomaly",
                    marker=dict(color="red",size=9)
                ))
        trend.update_layout(
            title=f"{kpi_w.value} Trend with Anomalies",
            height=350, template="plotly_white",
            legend=dict(orientation="h",y=1.12)
        )
        trend_html = trend.to_html(full_html=False,include_plotlyjs="cdn")

        counts = a[severity_col].astype(str).str.title().value_counts() if not a.empty else pd.Series(dtype=int)
        labs = ["Critical","High","Watch"]
        vals = [int(counts.get(x,0)) for x in labs]
        pf = go.Figure(go.Pie(
            labels=labs, values=vals, hole=.6,
            marker_colors=["#f04438","#ff8a00","#f4c430"],
            textinfo="label+value"
        ))
        pf.update_layout(
            title="Alerts by Priority", height=320, template="plotly_white",
            annotations=[dict(text=f"{sum(vals)}<br>Alerts",x=.5,y=.5,showarrow=False)]
        )
        priority_html = pf.to_html(full_html=False,include_plotlyjs=False)

        selected = date_w.value
        pday = p[p.Date == pd.Timestamp(selected)] if selected else p.iloc[0:0]
        if pday.empty and selected:
            pday = prod[prod.Date == pd.Timestamp(selected)]
        metric = cfg["product"]
        category_html = "<p>No category data available.</p>"
        product_html = "<p>No product data available.</p>"

        if not pday.empty and "Category" in pday and metric in pday:
            cd = pday.groupby("Category",as_index=False)[metric].sum()
            cf = px.pie(cd,names="Category",values=metric,hole=.35,title="KPI by Category")
            category_html = cf.to_html(full_html=False,include_plotlyjs=False)

        if not pday.empty and "Product_Name" in pday and metric in pday:
            pdx = pday.groupby("Product_Name",as_index=False)[metric].sum().sort_values(metric,ascending=False).head(10)
            pf2 = px.bar(pdx,x=metric,y="Product_Name",orientation="h",title="Top Products by KPI")
            pf2.update_layout(yaxis=dict(autorange="reversed"))
            product_html = pf2.to_html(full_html=False,include_plotlyjs=False)

        if not a.empty:
            feed = a.copy()
            feed["_sev"] = feed[severity_col].astype(str).str.lower().map(
                {"critical":0,"high":1,"watch":2,"normal":3}
            ).fillna(4)
            feed["_dev"] = pd.to_numeric(
                feed.get("Max_Absolute_Deviation_Pct",0),errors="coerce"
            ).abs()
            feed = feed.sort_values(["_sev","_dev"],ascending=[True,False]).head(10)
            feed.insert(0,"Rank",range(1,len(feed)+1))

            def val_col(col):
                return feed[col] if col and col in feed else pd.Series(["—"]*len(feed),index=feed.index)

            shown = pd.DataFrame({
                "Rank":feed["Rank"],
                "Date":feed.Date.dt.strftime("%d-%b-%Y"),
                "Severity":val_col(severity_col),
                "KPI Count":val_col(kpi_count_col),
                "Max Deviation %":pd.to_numeric(val_col("Max_Absolute_Deviation_Pct"),errors="coerce").map(
                    lambda x:f"{x:.2f}%" if pd.notna(x) else "—"
                ),
                "Priority":val_col("Alert_Priority"),
                "Owner":val_col(owner_col),
                "Supporting Owner":val_col(support_col)
            })
            feed_html = shown.to_html(index=False,escape=True,classes="feed")
        else:
            feed_html = "<p>No alerts found.</p>"

        narrative = narrative_state["text"] if narrative_state["date"] == selected else ""
        if not narrative and narrative_col and selected:
            nr = alerts[alerts.Date == pd.Timestamp(selected)]
            if not nr.empty:
                narrative = str(nr.iloc[-1].get(narrative_col,"") or "")
        if not narrative or narrative.lower() == "nan":
            narrative = "No saved narrative for this date. Generate the narrative before exporting to include it."

        page = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>E-Commerce Anomaly Monitoring Dashboard</title>
{dashboard_css()}
</head><body>
<div class="dash">
<div class="hero"><h1>🛒 E-Commerce Anomaly Monitoring Dashboard</h1>
<p>AI-assisted detection • KPI monitoring • Evidence-led investigation • Action ownership</p>
<p>{start:%d %b %Y} – {end:%d %b %Y}</p></div>
<div class="cards">{''.join(cards)}</div>
<div class="row2"><div class="panel">{trend_html}</div><div class="panel">{priority_html}</div></div>
<div class="row3"><div class="panel"><div class="title">Category Investigation</div>{category_html}</div>
<div class="panel"><div class="title">Product Investigation</div>{product_html}</div></div>
<div class="panel"><div class="title">Actionable Alert Feed</div>
<p>10 highest-priority anomalies requiring attention.</p>{feed_html}</div>
<div class="panel"><div class="title">Alert Narrative & Investigation • {selected or 'Selected date'}</div>
<pre>{html.escape(narrative)}</pre></div>
<p style="font-size:11px;color:#66758b">Exported snapshot. Plotly charts retain hover/zoom. Colab filters and live Gemini generation do not remain interactive in this HTML. Root causes are hypotheses, not confirmed causes.</p>
</div></body></html>"""

        path = "/content/Ecommerce_Anomaly_Dashboard.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)

        print("HTML dashboard created. Starting download...")
        files.download(path)

# -------------------- 7. WIRE CONTROLS --------------------------

refresh_btn.on_click(render_dashboard)
export_btn.on_click(export_dashboard)
narrative_btn.on_click(generate_narrative)

for control in [
    start_w, end_w, kpi_w, geo_w, cat_w, priority_w, date_w
]:
    control.observe(render_dashboard, names="value")

display(HTML("""
<h2 style="font-family:Arial;color:#123b79">
E-Commerce Anomaly Monitoring Dashboard
</h2>
<p>Choose filters and a KPI, select an investigation date, generate a narrative, or export the current dashboard.</p>
"""))

display(widgets.VBox([
    widgets.HBox([start_w, end_w]),
    widgets.HBox([kpi_w, geo_w, cat_w, priority_w]),
    widgets.HBox([date_w, narrative_btn, export_btn, refresh_btn]),
    message_out
]))

display(dashboard_out)
render_dashboard()
