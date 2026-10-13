
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================
st.set_page_config(
    page_title="E-Commerce Anomaly Intelligence",
    page_icon="📊",
    layout="wide"
)


# ==================================================
# 1A. DASHBOARD STYLING — HIGH CONTRAST AND CLEAN SPACING
# ==================================================

st.markdown(
    """
    <style>
    /* White dashboard background */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        background: #FFFFFF !important;
        color: #263238 !important;
    }

    .block-container {
        max-width: 100%;
        padding: 0.8rem 1rem 1.2rem 1rem;
    }

    /* Dark, readable headings and body text */
    
/* Dark, readable text across the dashboard */
h1, h2, h3, h4,
[data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"],
label {
    color: #263238 !important;
    opacity: 1 !important;
}

/* Restore white text specifically inside the blue header */
[data-testid="stMarkdownContainer"] h1 {
    color: #FFFFFF !important;
}

    h1, h2, h3, h4 {
        font-weight: 700 !important;
    }

    [data-testid="stCaptionContainer"] {
        font-size: 0.85rem !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        border-right: 1px solid #CBD5E1 !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: #263238 !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        background: #FFFFFF !important;
        color: #263238 !important;
        border: 1px solid #AAB6C5 !important;
    }

    /* Consistent column alignment and less unnecessary space */
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
        gap: 0.8rem !important;
        align-items: stretch !important;
    }

    [data-testid="stMain"] [data-testid="column"] {
        background: #FFFFFF !important;
        border: 1px solid #D5DCE5 !important;
        border-radius: 8px !important;
        padding: 0.65rem !important;
        box-shadow: none !important;
        min-width: 0 !important;
    }

    [data-testid="stVerticalBlock"] {
        gap: 0.55rem;
    }

    /* Charts and tables */
    [data-testid="stPlotlyChart"],
    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background: #FFFFFF !important;
        border: 1px solid #D5DCE5 !important;
        border-radius: 5px !important;
    }

    [data-testid="stPlotlyChart"] > div {
        background: #FFFFFF !important;
    }

    hr {
        border-color: #D5DCE5 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

BASE_DIR = Path(__file__).parent

# ==================================================
# 2. LOAD THE SIX CSV FILES
# ==================================================
@st.cache_data
def load_csv(filename):
    path = BASE_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

detected = load_csv("detected.csv")
alerts = load_csv("alert_summary.csv")
products = load_csv("product_data.csv")
category_summary = load_csv("category_summary.csv")
geography_summary = load_csv("geography_summary.csv")
product_summary = load_csv("product_summary.csv")

if detected.empty or alerts.empty or products.empty:
    st.error(
        "Required CSV data is missing or empty. "
        "Ensure all six CSV files are in the same GitHub repository "
        "folder as app.py."
    )
    st.stop()

for df in [detected, alerts, products]:
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

detected = detected.dropna(subset=["Date"]).copy()
alerts = alerts.dropna(subset=["Date"]).copy()
products = products.dropna(subset=["Date"]).copy()

# ==================================================
# 3. KPI DEFINITIONS
# ==================================================
KPI_OPTIONS = {
    "Orders": (
        "Total_Orders",
        "Total_Orders_Expected",
        "Total_Orders_Deviation_Pct",
        "Orders_Is_Anomaly"
    ),
    "Revenue": (
        "Total_Revenue_INR",
        "Total_Revenue_INR_Expected",
        "Total_Revenue_INR_Deviation_Pct",
        "Revenue_Is_Anomaly"
    ),
    "Average Order Value": (
        "Weighted_AOV_INR",
        "Weighted_AOV_INR_Expected",
        "Weighted_AOV_INR_Deviation_Pct",
        "AOV_Is_Anomaly"
    ),
    "Cancellation Rate": (
        "Avg_Cancellation_Rate_Pct",
        "Avg_Cancellation_Rate_Pct_Expected",
        "Avg_Cancellation_Rate_Pct_Deviation_Pct",
        "Cancellation_Rate_Is_Anomaly"
    )
}

def number(value, digits=2):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.{digits}f}"
    except (ValueError, TypeError):
        return "N/A"

def is_true(value):
    return str(value).strip().lower() in ("true", "1", "yes")

def get_priority(row):
    value = row.get("Alert_Priority")
    if pd.notna(value) and str(value).strip():
        return str(value)

    severity = str(
        row.get("Overall_Anomaly_Severity", "Normal")
    ).strip().title()

    return {
        "Critical": "P1 - Immediate",
        "High": "P2 - High",
        "Watch": "P3 - Watch",
        "Normal": "P4 - Normal"
    }.get(severity, "P4 - Normal")

def build_narrative(row):
    affected = []

    for label, columns in KPI_OPTIONS.items():
        flag_column = columns[3]
        if flag_column in row.index and is_true(row[flag_column]):
            affected.append(label)

    if affected:
        affected_text = ", ".join(affected)
    else:
        affected_text = "One or more business KPIs"

    severity = str(row.get("Overall_Anomaly_Severity", "Unknown"))

    if len(affected) >= 3:
        hypothesis = (
            "A broad-based operational or business disruption may be "
            "affecting multiple KPIs. Check order processing, system "
            "availability, inventory and recent business changes."
        )
        confidence = "Moderate: several KPIs are affected"
    elif "Cancellation Rate" in affected:
        hypothesis = (
            "A change in cancellations may relate to payment, fulfilment, "
            "stock availability or customer experience. Validate against "
            "operational records before concluding."
        )
        confidence = "Low to moderate: further investigation required"
    elif "Orders" in affected or "Revenue" in affected:
        hypothesis = (
            "A demand, product availability, pricing, marketing or "
            "order-processing change may explain the movement. Compare "
            "category and geography evidence."
        )
        confidence = "Low to moderate: further investigation required"
    else:
        hypothesis = (
            "The selected day contains a detected anomaly. Investigate "
            "the KPI deviations and product-level evidence before "
            "assigning a cause."
        )
        confidence = "Low: evidence is inconclusive"

    evidence = []
    for label, columns in KPI_OPTIONS.items():
        deviation_column = columns[2]
        if (
            deviation_column in row.index
            and pd.notna(row[deviation_column])
        ):
            evidence.append(
                f"{label}: {number(row[deviation_column])}% deviation"
            )

    return affected_text, hypothesis, confidence, evidence

# ==================================================
# 4. HEADER
# ==================================================

# ==================================================
# 4. HEADER
# ==================================================

st.markdown(
    """
    <div style="
        background: linear-gradient(110deg, #10284A, #245B86);
        padding: 24px;
        border-radius: 12px;
        color: #FFFFFF !important;
        margin-bottom: 8px;
    ">
        <h1 style="
            margin: 0;
            color: #FFFFFF !important;
            font-size: 32px;
            font-weight: 800;
            line-height: 1.25;
        ">
            E-Commerce Anomaly Intelligence
        </h1>
        
<p style="
    margin: 12px 0 0 0;
    color: #FFFFFF !important;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.5;
    opacity: 1;
    text-shadow: 0 1px 2px rgba(0,0,0,0.35);
">
    Sales monitoring · Root-cause investigation · Action ownership
</p>

    </div>
    """,
    unsafe_allow_html=True
)

st.caption(
    "Historical-data monitoring prototype. Anomaly alerts are signals "
    "for investigation, not proof of root cause."
)

# ==================================================
# 5. FILTERS
# ==================================================
st.sidebar.header("Dashboard Filters")

minimum_date = detected["Date"].min().date()
maximum_date = detected["Date"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
    start_date = end_date = date_range[0]
else:
    start_date, end_date = minimum_date, maximum_date



geo_options = ["All"]
if "Geography" in products.columns:
    geo_options += sorted(
        products["Geography"].dropna().astype(str).unique().tolist()
    )

category_options = ["All"]
if "Category" in products.columns:
    category_options += sorted(
        products["Category"].dropna().astype(str).unique().tolist()
    )

geo = st.sidebar.selectbox("Geography", geo_options)
category = st.sidebar.selectbox("Category", category_options)

alerts["Display_Priority"] = alerts.apply(get_priority, axis=1)

priority_options = sorted(
    alerts["Display_Priority"].dropna().unique().tolist()
)

selected_priorities = st.sidebar.multiselect(
    "Alert priority",
    priority_options,
    default=priority_options
)

# ==================================================
# 6. FILTER DATA
# ==================================================
det = detected[
    detected["Date"].dt.date.between(start_date, end_date)
].copy()

alert_data = alerts[
    alerts["Date"].dt.date.between(start_date, end_date)
].copy()

alert_data = alert_data[
    alert_data["Display_Priority"].isin(selected_priorities)
].copy()

prod = products[
    products["Date"].dt.date.between(start_date, end_date)
].copy()

if geo != "All" and "Geography" in prod.columns:
    prod = prod[prod["Geography"].astype(str) == geo]

if category != "All" and "Category" in prod.columns:
    prod = prod[prod["Category"].astype(str) == category]

if det.empty:
    st.warning("No daily records exist for the selected date range.")
    st.stop()


# ==================================================
# 7. KPI CARDS — SELECTED DATE RANGE
# ==================================================
st.subheader("Business Performance Overview")

# 'det' already contains daily data filtered to the selected date range.
range_orders = det["Total_Orders"].sum()
range_revenue = det["Total_Revenue_INR"].sum()

# Weighted AOV for the entire selected range
range_aov = (
    range_revenue / range_orders
    if range_orders and range_orders != 0
    else 0
)

# Average of daily cancellation rates in the selected range
range_cancellation = det[
    "Avg_Cancellation_Rate_Pct"
].mean()

# Display the selected range clearly
st.caption(
    f"Summary for {start_date:%d %b %Y} – {end_date:%d %b %Y}"
)

# Format the KPI values
orders_text = f"{range_orders:,.0f}"
revenue_text = f"₹{range_revenue:,.0f}"
aov_text = f"₹{range_aov:,.2f}"
cancellation_text = (
    f"{range_cancellation:.2f}%"
    if pd.notna(range_cancellation)
    else "N/A"
)

# Custom visual styling for the KPI cards
st.markdown(
    """
    <style>
    .kpi-card {
        position: relative;
        background: #FFFFFF !important;
        border: 1px solid #D8E0EA;
        border-top: 4px solid #64748B;
        border-radius: 12px;
        padding: 16px 17px 15px;
        min-height: 126px;
        color: #172B46;
        box-shadow: 0 3px 10px rgba(25, 45, 75, 0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(25, 45, 75, 0.10);
    }
    [data-testid="stMain"] [data-testid="column"] .kpi-card {
        background: #FFFFFF !important;
    }
    .kpi-card.orders { border-top-color: #2878D0; }
    .kpi-card.revenue { border-top-color: #15966A; }
    .kpi-card.aov { border-top-color: #D97706; }
    .kpi-card.cancellation { border-top-color: #D9485F; }
    .kpi-topline {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 750;
        letter-spacing: 0.07em;
        color: #596B82;
        margin: 0;
    }
    .kpi-icon {
        display: inline-flex;
        width: 30px;
        height: 30px;
        align-items: center;
        justify-content: center;
        border-radius: 9px;
        background: #F2F5F9;
        font-size: 17px;
    }
    .orders .kpi-icon { background: #EAF3FF; }
    .revenue .kpi-icon { background: #E7F7F0; }
    .aov .kpi-icon { background: #FFF3E3; }
    .cancellation .kpi-icon { background: #FDECEF; }
    .kpi-value {
        font-size: 28px;
        font-weight: 800;
        color: #14243A;
        line-height: 1.2;
        overflow-wrap: anywhere;
        font-variant-numeric: tabular-nums;
    }
    .kpi-note {
        font-size: 11px;
        color: #718096;
        margin-top: 9px;
    }
    .priority-summary {
        border: 1px solid #DCE3EB;
        border-radius: 10px;
        background: #FFFFFF;
        padding: 12px 14px;
        margin-top: 8px;
        color: #24364B;
    }
    .priority-summary-title {
        font-size: 13px;
        font-weight: 750;
        color: #26384D;
        margin-bottom: 9px;
    }
    .priority-summary-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 5px 0;
        border-bottom: 1px solid #EDF0F4;
        font-size: 11px;
    }
    .priority-summary-row:last-child { border-bottom: 0; }
    .priority-summary-label { display: flex; align-items: center; gap: 7px; }
    .priority-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .priority-summary-count { font-weight: 750; font-variant-numeric: tabular-nums; }
    .priority-summary-note { font-size: 10px; line-height: 1.45; color: #718096; margin-top: 8px; }
    </style>
    """,
    unsafe_allow_html=True
)

# Four cards in one row
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card orders">
            <div class="kpi-topline"><div class="kpi-label">TOTAL ORDERS</div><span class="kpi-icon">▤</span></div>
            <div class="kpi-value">{orders_text}</div>
            <div class="kpi-note">Sum across selected dates</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card revenue">
            <div class="kpi-topline"><div class="kpi-label">TOTAL REVENUE</div><span class="kpi-icon">₹</span></div>
            <div class="kpi-value">{revenue_text}</div>
            <div class="kpi-note">Sum across selected dates</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card aov">
            <div class="kpi-topline"><div class="kpi-label">WEIGHTED AOV</div><span class="kpi-icon">↗</span></div>
            <div class="kpi-value">{aov_text}</div>
            <div class="kpi-note">Revenue ÷ orders</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi4:
    st.markdown(
        f"""
        <div class="kpi-card cancellation">
            <div class="kpi-topline"><div class="kpi-label">AVG. CANCELLATION RATE</div><span class="kpi-icon">%</span></div>
            <div class="kpi-value">{cancellation_text}</div>
            <div class="kpi-note">Average of daily rates</div>
        </div>
        """,
        unsafe_allow_html=True
    )





            






# ==================================================
# 8. INTERACTIVE KPI TREND + ALERTS BY PRIORITY
# ==================================================

# Toggle between side-by-side dashboard and expanded trend
expand_trend = st.checkbox(
    "Expand KPI Trend",
    value=False,
    key="expand_kpi_trend"
)

if expand_trend:
    trend_col = st.container()
    priority_col = None
else:
    trend_col, priority_col = st.columns([2.2, 1])


# --------------------------------------------------
# LEFT / FULL-WIDTH: KPI TREND
# --------------------------------------------------
with trend_col:
    st.subheader("KPI Trend with Anomalies")

    kpi_name = st.selectbox(
        "Select KPI",
        [
            "Orders",
            "Revenue (INR)",
            "Weighted AOV (INR)",
            "Cancellation Rate (%)"
        ],
        key="trend_kpi_selector"
    )

    trend_categories = ["All Categories"] + sorted(
        prod["Category"].dropna().astype(str).unique().tolist()
    )

    trend_category = st.selectbox(
        "Select Category for Trend",
        trend_categories,
        key="trend_category_selector"
    )

    fig = go.Figure()

    # --------------------------------------------------
    # OVERALL TREND: ORIGINAL DETECTOR RESULTS
    # --------------------------------------------------
    if trend_category == "All Categories":
        trend = det.copy()
        trend["Date"] = pd.to_datetime(
            trend["Date"], errors="coerce"
        )
        trend = trend.dropna(subset=["Date"]).sort_values("Date")

        trend_columns = {
            "Orders": (
                "Total_Orders",
                "Total_Orders_Expected",
                "Orders_Is_Anomaly"
            ),
            "Revenue (INR)": (
                "Total_Revenue_INR",
                "Total_Revenue_INR_Expected",
                "Revenue_Is_Anomaly"
            ),
            "Weighted AOV (INR)": (
                "Weighted_AOV_INR",
                "Weighted_AOV_INR_Expected",
                "AOV_Is_Anomaly"
            ),
            "Cancellation Rate (%)": (
                "Avg_Cancellation_Rate_Pct",
                "Avg_Cancellation_Rate_Pct_Expected",
                "Cancellation_Rate_Is_Anomaly"
            )
        }

        actual_col, expected_col, flag_col = trend_columns[kpi_name]

        if actual_col not in trend.columns:
            st.warning(f"Missing KPI column: {actual_col}")
        else:
            fig.add_trace(go.Scatter(
                x=trend["Date"],
                y=trend[actual_col],
                mode="lines+markers",
                name=kpi_name,
                line=dict(color="#2675C9", width=2),
                marker=dict(size=4),
                hovertemplate=(
                    "%{x|%d %b %Y}<br>"
                    + kpi_name
                    + ": %{y:,.2f}<extra></extra>"
                )
            ))

            if expected_col in trend.columns:
                fig.add_trace(go.Scatter(
                    x=trend["Date"],
                    y=trend[expected_col],
                    mode="lines",
                    name="Expected baseline",
                    line=dict(
                        color="#E67E22",
                        width=3,
                        dash="dash"
                    ),
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>"
                        "Expected: %{y:,.2f}<extra></extra>"
                    )
                ))

            if flag_col in trend.columns:
                anomaly_mask = trend[flag_col].apply(is_true)
                anomaly_data = trend[
                    anomaly_mask
                ].dropna(subset=[actual_col])

                if not anomaly_data.empty:
                    fig.add_trace(go.Scatter(
                        x=anomaly_data["Date"],
                        y=anomaly_data[actual_col],
                        mode="markers",
                        name="Anomaly",
                        marker=dict(
                            color="#FF3B30",
                            size=9,
                            symbol="circle"
                        ),
                        hovertemplate=(
                            "%{x|%d %b %Y}<br>"
                            "Anomaly: %{y:,.2f}<extra></extra>"
                        )
                    ))

    # --------------------------------------------------
    # CATEGORY TREND: LEAVE-ONE-OUT WEEKDAY BASELINE
    # --------------------------------------------------
    else:
        category_history = prod[
            prod["Category"].astype(str) == trend_category
        ].copy()

        category_history["Date"] = pd.to_datetime(
            category_history["Date"], errors="coerce"
        )
        category_history = category_history.dropna(
            subset=["Date"]
        )

        if category_history.empty:
            st.warning("No data is available for this category.")
        else:
            for col in [
                "Orders",
                "Revenue_INR",
                "Cancellation_Rate_Pct"
            ]:
                category_history[col] = pd.to_numeric(
                    category_history[col], errors="coerce"
                )

            daily = (
                category_history.groupby("Date", as_index=False)
                .agg(
                    Orders=("Orders", "sum"),
                    Revenue_INR=("Revenue_INR", "sum")
                )
            )

            daily["Weighted AOV (INR)"] = (
                daily["Revenue_INR"]
                / daily["Orders"].replace(0, float("nan"))
            )

            category_history["Weighted_Cancellation"] = (
                category_history["Cancellation_Rate_Pct"]
                * category_history["Orders"]
            )

            cancellation_sum = category_history.groupby("Date")[
                "Weighted_Cancellation"
            ].sum()

            orders_by_date = category_history.groupby("Date")[
                "Orders"
            ].sum()

            daily["Cancellation Rate (%)"] = (
                daily["Date"].map(cancellation_sum)
                / daily["Date"].map(orders_by_date).replace(
                    0, float("nan")
                )
            )

            daily = daily.sort_values("Date").copy()
            daily["Day_of_Week"] = daily["Date"].dt.dayofweek

            metric_columns = {
                "Orders": "Orders",
                "Revenue (INR)": "Revenue_INR",
                "Weighted AOV (INR)": "Weighted AOV (INR)",
                "Cancellation Rate (%)": "Cancellation Rate (%)"
            }
            metric_col = metric_columns[kpi_name]

            # Build baseline using all available category dates,
            # excluding each date from its own reference calculation.
            history = daily.copy().sort_values("Date").reset_index(
                drop=True
            )
            history["Expected"] = float("nan")
            history["MAD"] = float("nan")

            for idx in history.index:
                weekday = history.loc[idx, "Day_of_Week"]

                reference = history.loc[
                    (history["Day_of_Week"] == weekday)
                    & (history.index != idx),
                    metric_col
                ].dropna()

                if len(reference) < 2:
                    reference = history.loc[
                        history.index != idx, metric_col
                    ].dropna()

                if not reference.empty:
                    expected_value = reference.median()
                    mad_value = (
                        reference - expected_value
                    ).abs().median()

                    history.loc[idx, "Expected"] = expected_value
                    history.loc[idx, "MAD"] = mad_value

            daily = daily.merge(
                history[["Date", "Expected", "MAD"]],
                on="Date",
                how="left"
            )

            daily["Deviation"] = (
                daily[metric_col] - daily["Expected"]
            ).abs()

            metric_median = history[metric_col].median()
            metric_scale = max(
                abs(float(metric_median))
                if pd.notna(metric_median) else 0.0,
                1.0
            )
            tolerance = metric_scale * 0.01

            daily["Is_Anomaly"] = (
                daily["Expected"].notna()
                & daily["MAD"].notna()
                & (
                    (
                        (daily["MAD"] > 0)
                        & (daily["Deviation"] > 3 * daily["MAD"])
                    )
                    | (
                        (daily["MAD"] == 0)
                        & (daily["Deviation"] > tolerance)
                    )
                )
            )

            range_start = pd.to_datetime(start_date).normalize()
            range_end = pd.to_datetime(end_date).normalize()

            daily = daily[
                (daily["Date"] >= range_start)
                & (daily["Date"] < range_end + pd.Timedelta(days=1))
            ].copy()

            if daily.empty:
                st.info(
                    "No records exist for this category in the selected "
                    "date range."
                )
            else:
                fig.add_trace(go.Scatter(
                    x=daily["Date"],
                    y=daily[metric_col],
                    mode="lines+markers",
                    name=f"{kpi_name} — {trend_category}",
                    line=dict(color="#2675C9", width=2),
                    marker=dict(size=4),
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>"
                        + kpi_name
                        + ": %{y:,.2f}<extra></extra>"
                    )
                ))

                fig.add_trace(go.Scatter(
                    x=daily["Date"],
                    y=daily["Expected"],
                    mode="lines+markers",
                    name="Expected weekday baseline",
                    line=dict(
                        color="#E67E22",
                        width=3,
                        dash="dash"
                    ),
                    marker=dict(
                        size=6,
                        color="#E67E22",
                        symbol="diamond"
                    ),
                    connectgaps=False,
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>"
                        "Expected: %{y:,.2f}<extra></extra>"
                    )
                ))

                anomaly_data = daily[
                    daily["Is_Anomaly"].fillna(False)
                ].dropna(subset=[metric_col])

                if not anomaly_data.empty:
                    fig.add_trace(go.Scatter(
                        x=anomaly_data["Date"],
                        y=anomaly_data[metric_col],
                        mode="markers",
                        name="Potential anomaly",
                        marker=dict(
                            color="#FF3B30",
                            size=10,
                            symbol="circle"
                        ),
                        hovertemplate=(
                            "%{x|%d %b %Y}<br>"
                            "Potential anomaly: %{y:,.2f}"
                            "<extra></extra>"
                        )
                    ))

                st.caption(
                    "Category baseline uses a leave-one-out weekday median, "
                    "with a fallback to other historical dates. Category "
                    "anomaly markers are exploratory and are not the "
                    "original detector's alerts."
                )

    # --------------------------------------------------
    # DISPLAY TREND
    # --------------------------------------------------
    fig.update_layout(
        height=520 if expand_trend else 300,
        margin=dict(l=10, r=10, t=25, b=10),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(size=10 if expand_trend else 9)
        ),
        xaxis_title=None,
        yaxis_title=None
    )

    fig.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(
        gridcolor="#E7ECF2",
        zeroline=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "displaylogo": False
        }
    )


# --------------------------------------------------
# RIGHT: ALERTS BY PRIORITY
# Hidden while trend is expanded
# --------------------------------------------------
if not expand_trend:
    with priority_col:
        st.subheader("Alerts by Priority")

        priority_source = alert_data.copy()

        if not priority_source.empty and not prod.empty:
            matching_products = prod.copy()

            if geo != "All" and "Geography" in matching_products.columns:
                matching_products = matching_products[
                    matching_products["Geography"].astype(str) == str(geo)
                ]

            if category != "All" and "Category" in matching_products.columns:
                matching_products = matching_products[
                    matching_products["Category"].astype(str) == str(category)
                ]

            matching_dates = set(
                pd.to_datetime(matching_products["Date"]).dt.date
            )

            priority_source = priority_source[
                pd.to_datetime(priority_source["Date"]).dt.date.isin(
                    matching_dates
                )
            ]

        if not priority_source.empty:
            priority_counts = (
                priority_source["Display_Priority"]
                .value_counts()
                .rename_axis("Priority")
                .reset_index(name="Alerts")
            )

            total_alerts = int(priority_counts["Alerts"].sum())

            if total_alerts > 0:
                priority_labels = {
                    "P1 - Immediate": "Critical",
                    "P2 - High": "High",
                    "P3 - Watch": "Watch",
                    "P4 - Normal": "Normal"
                }

                priority_counts["Priority_Label"] = (
                    priority_counts["Priority"]
                    .map(priority_labels)
                    .fillna(priority_counts["Priority"])
                )

                priority_counts["Percentage"] = (
                    priority_counts["Alerts"] / total_alerts * 100
                )

                priority_colors = {
                    "Critical": "#FF3B30",
                    "High": "#FF7A00",
                    "Watch": "#FFBF00",
                    "Normal": "#36A269"
                }

                priority_fig = px.pie(
                    priority_counts,
                    names="Priority_Label",
                    values="Alerts",
                    hole=0.62,
                    color="Priority_Label",
                    color_discrete_map=priority_colors
                )

                priority_fig.update_traces(
                    text=priority_counts["Percentage"].map(
                        lambda value: f"{value:.0f}%"
                    ),
                    textinfo="text",
                    textposition="inside",
                    insidetextorientation="horizontal",
                    textfont=dict(size=11, color="white"),
                    sort=False,
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        "Alerts: %{value}<br>"
                        "Share: %{percent}<extra></extra>"
                    )
                )

                priority_fig.update_layout(
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    height=240,
                    margin=dict(l=0, r=0, t=5, b=5),
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        x=1.0,
                        y=0.5,
                        xanchor="left",
                        yanchor="middle",
                        font=dict(size=10)
                    ),
                    uniformtext=dict(
                        minsize=9,
                        mode="hide"
                    ),
                    annotations=[
                        dict(
                            text=f"<b>{total_alerts}</b><br>Alerts",
                            x=0.5,
                            y=0.5,
                            xref="paper",
                            yref="paper",
                            xanchor="center",
                            yanchor="middle",
                            showarrow=False,
                            align="center",
                            font=dict(size=15, color="#23344D")
                        )
                    ]
                )

                st.plotly_chart(
                    priority_fig,
                    use_container_width=True,
                    config={"displayModeBar": False}
                )

                st.caption(
                    f"Geography: {geo} | Category: {category}"
                )
            else:
                st.info("No alerts match the selected filters.")
        else:
            st.info("No alerts match the selected filters.")

        # Compact response summary fills the unused space below the donut
        # and gives users a quick operational interpretation of the alert mix.
        summary_source = priority_source.copy()
        if not summary_source.empty:
            summary_counts = summary_source["Display_Priority"].value_counts().to_dict()
        else:
            summary_counts = {}

        critical_count = int(summary_counts.get("P1 - Immediate", 0))
        high_count = int(summary_counts.get("P2 - High", 0))
        watch_count = int(summary_counts.get("P3 - Watch", 0))
        total_visible_alerts = critical_count + high_count + watch_count + int(summary_counts.get("P4 - Normal", 0))

        if critical_count > 0:
            response_message = "Start with the critical alerts and validate the affected business process."
        elif high_count > 0:
            response_message = "Review high-priority alerts and confirm whether the deviation is persistent."
        elif watch_count > 0:
            response_message = "No immediate critical alerts; keep watch-level deviations under monitoring."
        else:
            response_message = "No priority alerts are currently visible for these filters."

        st.markdown(
            f"""
            <div class="priority-summary">
                <div class="priority-summary-title">Response at a glance</div>
                <div class="priority-summary-row">
                    <span class="priority-summary-label"><span class="priority-dot" style="background:#FF3B30"></span>Immediate triage</span>
                    <span class="priority-summary-count">{critical_count} critical</span>
                </div>
                <div class="priority-summary-row">
                    <span class="priority-summary-label"><span class="priority-dot" style="background:#FF7A00"></span>Investigate next</span>
                    <span class="priority-summary-count">{high_count} high</span>
                </div>
                <div class="priority-summary-row">
                    <span class="priority-summary-label"><span class="priority-dot" style="background:#FFBF00"></span>Continue monitoring</span>
                    <span class="priority-summary-count">{watch_count} watch</span>
                </div>
                <div class="priority-summary-note">{response_message}</div>
            </div>
            """,
            unsafe_allow_html=True
        )



# ==========================================================
# SECTIONS 9 & 10: CATEGORY + PRODUCT INVESTIGATION
# ==========================================================

category_col, product_col = st.columns([1, 1])

# ----------------------------------------------------------
# PREPARE INVESTIGATION DATA
# ----------------------------------------------------------

investigation_data = products.copy()

investigation_data["Date"] = pd.to_datetime(
    investigation_data["Date"], errors="coerce"
)

for col in [
    "Orders",
    "Revenue_INR",
    "AOV_INR",
    "Cancellation_Rate_Pct",
]:
    if col in investigation_data.columns:
        investigation_data[col] = pd.to_numeric(
            investigation_data[col], errors="coerce"
        )

required_columns = [
    "Date", "Category", "Product_Name", "Orders",
    "Revenue_INR", "Cancellation_Rate_Pct"
]

missing_columns = [
    col for col in required_columns
    if col not in investigation_data.columns
]

if missing_columns:
    st.error(
        "Investigation data is missing required columns: "
        + ", ".join(missing_columns)
    )
else:
    investigation_data = investigation_data.dropna(
        subset=["Date", "Category"]
    ).copy()

    range_start = pd.to_datetime(start_date).normalize()
    range_end = pd.to_datetime(end_date).normalize()

    # Full historical data, restricted to the selected geography.
    history_data = investigation_data.copy()

    if geo != "All":
        history_data = history_data[
            history_data["Geography"].astype(str) == str(geo)
        ].copy()

    # Actual data for the selected dates.
    selected_data = history_data[
        (history_data["Date"] >= range_start)
        & (
            history_data["Date"]
            < range_end + pd.Timedelta(days=1)
        )
    ].copy()

    # ------------------------------------------------------
    # COMMON KPI CONFIGURATION
    # ------------------------------------------------------

    KPI_CONFIG = {
        "Orders": {
            "column": "Orders",
            "kind": "sum",
            "label": "Orders",
            "format": "{:,.0f}",
        },
        "Revenue (INR)": {
            "column": "Revenue_INR",
            "kind": "sum",
            "label": "Revenue (INR)",
            "format": "₹{:,.2f}",
        },
        "Average Order Value (AOV)": {
            "column": "AOV_INR",
            "kind": "ratio",
            "label": "Average Order Value (₹)",
            "format": "₹{:,.2f}",
        },
        "Cancellation Rate (%)": {
            "column": "Cancellation_Rate_Pct",
            "kind": "rate",
            "label": "Cancellation Rate (%)",
            "format": "{:.2f}%",
        },
    }

    # ------------------------------------------------------
    # SECTION 9: CATEGORY INVESTIGATION
    # ------------------------------------------------------

    with category_col:
        st.subheader("Category Investigation")

        st.caption(
            "Compare actual category performance with a historical "
            "weekday baseline. The sidebar Category filter does not "
            "restrict this investigation."
        )

        category_kpi = st.selectbox(
            "Select KPI for Category Investigation",
            list(KPI_CONFIG.keys()),
            key="category_investigation_kpi",
        )

        cfg = KPI_CONFIG[category_kpi]

        if selected_data.empty or history_data.empty:
            st.info(
                "No data is available for the selected dates "
                "and geography."
            )
        else:
            # Daily category aggregates form the historical baseline.
            daily_category = (
                history_data.groupby(
                    ["Date", "Category"], as_index=False
                )
                .agg(
                    Daily_Orders=("Orders", "sum"),
                    Daily_Revenue=("Revenue_INR", "sum"),
                    Daily_Cancel_Weighted=(
                        "Cancellation_Rate_Pct",
                        lambda s: 0.0
                    ),
                )
            )

            # Calculate order-weighted cancellation rate correctly.
            history_data["_Cancel_Weighted"] = (
                history_data["Cancellation_Rate_Pct"]
                * history_data["Orders"].clip(lower=0)
            )

            cancel_daily = (
                history_data.groupby(
                    ["Date", "Category"], as_index=False
                )
                .agg(
                    Cancel_Weighted=("_Cancel_Weighted", "sum"),
                    Cancel_Orders=("Orders", "sum"),
                    Cancel_Mean=("Cancellation_Rate_Pct", "mean"),
                )
            )

            cancel_daily["Daily_Cancellation"] = (
                cancel_daily["Cancel_Weighted"]
                / cancel_daily["Cancel_Orders"].where(
                    cancel_daily["Cancel_Orders"] > 0
                )
            )

            cancel_daily["Daily_Cancellation"] = (
                cancel_daily["Daily_Cancellation"].fillna(
                    cancel_daily["Cancel_Mean"]
                )
            )

            daily_category = daily_category.drop(
                columns=["Daily_Cancel_Weighted"]
            ).merge(
                cancel_daily[
                    ["Date", "Category", "Daily_Cancellation"]
                ],
                on=["Date", "Category"],
                how="left",
            )

            # AOV = daily revenue / daily orders.
            daily_category["Daily_AOV"] = (
                daily_category["Daily_Revenue"]
                / daily_category["Daily_Orders"].where(
                    daily_category["Daily_Orders"] > 0
                )
            )

            daily_category["Day_of_Week"] = (
                daily_category["Date"].dt.dayofweek
            )

            # Choose the appropriate daily KPI for the baseline.
            baseline_column = {
                "Orders": "Daily_Orders",
                "Revenue (INR)": "Daily_Revenue",
                "Average Order Value (AOV)": "Daily_AOV",
                "Cancellation Rate (%)": "Daily_Cancellation",
            }[category_kpi]

            weekday_baseline = (
                daily_category.groupby(
                    ["Day_of_Week", "Category"]
                )[baseline_column]
                .median()
                .rename("Weekday_Baseline")
                .reset_index()
            )

            # Build every date/category combination in the selected range.
            expected_dates = pd.DataFrame({
                "Date": pd.date_range(
                    range_start, range_end, freq="D"
                )
            })

            expected_dates["Day_of_Week"] = (
                expected_dates["Date"].dt.dayofweek
            )

            category_list = sorted(
                history_data["Category"].dropna().unique()
            )

            expected_dates["_join_key"] = 1

            categories_frame = pd.DataFrame({
                "Category": category_list,
                "_join_key": 1,
            })

            expected_grid = expected_dates.merge(
                categories_frame, on="_join_key"
            ).drop(columns="_join_key")

            expected_grid = expected_grid.merge(
                weekday_baseline,
                on=["Day_of_Week", "Category"],
                how="left",
            )

            # Counts and revenue are summed across selected dates.
            # AOV and cancellation rate are averaged across daily baselines.
            if cfg["kind"] == "sum":
                category_expected = (
                    expected_grid.groupby(
                        "Category", as_index=False
                    )
                    .agg(
                        Expected=(
                            "Weekday_Baseline",
                            lambda s: s.sum(min_count=1)
                        )
                    )
                )
            else:
                category_expected = (
                    expected_grid.groupby(
                        "Category", as_index=False
                    )
                    .agg(
                        Expected=("Weekday_Baseline", "mean")
                    )
                )

            # Calculate actual values for each category.
            actual_rows = []

            for cat, group in selected_data.groupby("Category"):
                orders = group["Orders"].sum()
                revenue = group["Revenue_INR"].sum()

                weighted_cancel = (
                    group["Cancellation_Rate_Pct"]
                    * group["Orders"].clip(lower=0)
                ).sum()

                cancel_weight = group["Orders"].clip(lower=0).sum()

                cancellation_rate = (
                    weighted_cancel / cancel_weight
                    if cancel_weight > 0
                    else group["Cancellation_Rate_Pct"].mean()
                )

                actual_rows.append({
                    "Category": cat,
                    "Actual_Orders": orders,
                    "Actual_Revenue": revenue,
                    "Actual_AOV": (
                        revenue / orders
                        if pd.notna(orders) and orders > 0
                        else float("nan")
                    ),
                    "Actual_Cancellation": cancellation_rate,
                })

            category_actual = pd.DataFrame(actual_rows)

            actual_column = {
                "Orders": "Actual_Orders",
                "Revenue (INR)": "Actual_Revenue",
                "Average Order Value (AOV)": "Actual_AOV",
                "Cancellation Rate (%)": "Actual_Cancellation",
            }[category_kpi]

            results = category_expected.merge(
                category_actual, on="Category", how="outer"
            )

            results["Actual"] = pd.to_numeric(
                results[actual_column], errors="coerce"
            )

            results["Expected"] = pd.to_numeric(
                results["Expected"], errors="coerce"
            )

            # Positive gap always means an unfavourable result.
            if category_kpi == "Cancellation Rate (%)":
                results["Gap"] = (
                    results["Actual"] - results["Expected"]
                )
            else:
                results["Gap"] = (
                    results["Expected"] - results["Actual"]
                )

            results["Status"] = results["Gap"].apply(
                lambda x: (
                    "Below expectation" if x > 0
                    else "Better than expected" if x < 0
                    else "At expectation"
                ) if pd.notna(x) else "Baseline unavailable"
            )

            positive_gap = results["Gap"].clip(lower=0).sum()

            results["Contribution_Pct"] = (
                results["Gap"].clip(lower=0)
                / positive_gap * 100
                if positive_gap > 0
                else 0.0
            )

            results = results.sort_values(
                "Gap", ascending=False, na_position="last"
            )

            st.markdown(
                f"**{cfg['label']} — actual vs expected by category**"
            )

            chart_data = results.dropna(
                subset=["Gap"]
            ).sort_values("Gap", ascending=True)

            if chart_data.empty:
                st.warning(
                    "A historical baseline is not available for "
                    "this KPI and filter selection."
                )
            else:
                category_fig = px.bar(
                    chart_data,
                    x="Gap",
                    y="Category",
                    orientation="h",
                    color="Status",
                    color_discrete_map={
                        "Below expectation": "#E74C3C",
                        "Better than expected": "#27AE60",
                        "At expectation": "#94A3B8",
                        "Baseline unavailable": "#94A3B8",
                    },
                    hover_data={
                        "Actual": ":,.2f",
                        "Expected": ":,.2f",
                        "Gap": ":,.2f",
                        "Contribution_Pct": ":.1f",
                    },
                    labels={
                        "Gap": "Unfavourable difference",
                        "Category": "",
                        "Status": "Performance",
                        "Contribution_Pct": "Share of adverse gap (%)",
                    },
                )

                category_fig.add_vline(
                    x=0,
                    line_width=1,
                    line_color="#64748B",
                )

            
                category_fig.update_layout(
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    height=360,
                    autosize=True,
                    margin=dict(l=12, r=12, t=35, b=35),
                    font=dict(
                        family="Arial, sans-serif",
                        size=13,
                        color="#263238"
                    ),
                    title_font=dict(
                        size=17,
                        color="#172B4D"
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        x=0,
                        font=dict(
                            size=11,
                            color="#263238"
                        )
                    ),
                    xaxis=dict(
                        title=dict(
                            text="Unfavourable difference",
                            font=dict(size=12, color="#263238")
                        ),
                        tickfont=dict(size=11, color="#344054"),
                        gridcolor="#E2E8F0",
                        zerolinecolor="#94A3B8",
                        automargin=True
                    ),
                    yaxis=dict(
                        title=None,
                        tickfont=dict(size=11, color="#344054"),
                        automargin=True
                    )
                )


                st.plotly_chart(
                    category_fig,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

                st.caption(
                    "Red indicates an unfavourable gap; green indicates "
                    "better-than-expected performance. For cancellation "
                    "rate, an increase is unfavourable. These signals "
                    "support investigation and do not prove root cause."
                )

                with st.expander("View detailed category figures"):
                    detail_table = results[
                        [
                            "Category",
                            "Actual",
                            "Expected",
                            "Gap",
                            "Contribution_Pct",
                            "Status",
                        ]
                    ].rename(columns={
                        "Actual": f"Actual {cfg['label']}",
                        "Expected": f"Expected {cfg['label']}",
                        "Gap": "Unfavourable Gap",
                        "Contribution_Pct": "Share of Adverse Gap (%)",
                    })

                    st.dataframe(
                        detail_table,
                        use_container_width=True,
                        hide_index=True,
                    )

    # ------------------------------------------------------
    # SECTION 10: PRODUCT-LEVEL INVESTIGATION
    # ------------------------------------------------------

    with product_col:
        st.subheader("Product-Level Investigation")

        st.caption(
            "Investigate individual products. The sidebar Category "
            "filter applies to this panel."
        )

        product_filtered = selected_data.copy()

        if category != "All":
            product_filtered = product_filtered[
                product_filtered["Category"].astype(str)
                == str(category)
            ].copy()

        if product_filtered.empty:
            st.info(
                "No product data matches the selected dates, "
                "geography and category."
            )
        else:
            product_metric = st.selectbox(
                "Select KPI for Product Investigation",
                list(KPI_CONFIG.keys()),
                key="product_investigation_metric",
            )

            if product_metric == "Orders":
                product_summary = (
                    product_filtered.groupby(
                        "Product_Name", as_index=False
                    )
                    .agg(Value=("Orders", "sum"))
                )

            elif product_metric == "Revenue (INR)":
                product_summary = (
                    product_filtered.groupby(
                        "Product_Name", as_index=False
                    )
                    .agg(Value=("Revenue_INR", "sum"))
                )

            elif product_metric == "Average Order Value (AOV)":
                product_summary = (
                    product_filtered.groupby(
                        "Product_Name", as_index=False
                    )
                    .agg(
                        Revenue=("Revenue_INR", "sum"),
                        Orders=("Orders", "sum"),
                    )
                )

                product_summary["Value"] = (
                    product_summary["Revenue"]
                    / product_summary["Orders"].where(
                        product_summary["Orders"] > 0
                    )
                )

            else:
                product_filtered["_Cancel_Weighted"] = (
                    product_filtered["Cancellation_Rate_Pct"]
                    * product_filtered["Orders"].clip(lower=0)
                )

                product_summary = (
                    product_filtered.groupby(
                        "Product_Name", as_index=False
                    )
                    .agg(
                        Cancel_Weighted=("_Cancel_Weighted", "sum"),
                        Orders=("Orders", "sum"),
                    )
                )

                product_summary["Value"] = (
                    product_summary["Cancel_Weighted"]
                    / product_summary["Orders"].where(
                        product_summary["Orders"] > 0
                    )
                )

            product_summary = product_summary.dropna(
                subset=["Value"]
            )

            product_summary = product_summary[
                product_summary["Value"] >= 0
            ].sort_values("Value", ascending=False)

            if product_summary.empty or product_summary["Value"].sum() <= 0:
                st.info(
                    "No positive values are available for this KPI "
                    "under the selected filters."
                )
            else:
                # Keep the chart readable: top 7 products + other products.
                top_n = 7

                if len(product_summary) > top_n:
                    top_products = product_summary.head(top_n)[
                        ["Product_Name", "Value"]
                    ].copy()

                    other_value = product_summary.iloc[top_n:][
                        "Value"
                    ].sum()

                    if other_value > 0:
                        top_products = pd.concat(
                            [
                                top_products,
                                pd.DataFrame({
                                    "Product_Name": ["Other products"],
                                    "Value": [other_value],
                                }),
                            ],
                            ignore_index=True,
                        )

                    product_chart_data = top_products
                else:
                    product_chart_data = product_summary[
                        ["Product_Name", "Value"]
                    ].copy()

                product_fig = px.pie(
                    product_chart_data,
                    names="Product_Name",
                    values="Value",
                    hole=0.42,
                    title=f"{product_metric} by Product",
                )

                product_fig.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        "Value: %{value:,.2f}<br>"
                        "Share: %{percent}<extra></extra>"
                    ),
                )

                
                product_fig.update_layout(
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    height=360,
                    autosize=True,
                    margin=dict(l=12, r=12, t=45, b=55),
                    font=dict(
                        family="Arial, sans-serif",
                        size=13,
                        color="#263238"
                    ),
                    title=dict(
                        text=f"{product_metric} by Product",
                        font=dict(size=17, color="#172B4D"),
                        x=0.02,
                        xanchor="left"
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.08,
                        x=0,
                        font=dict(size=10, color="#263238")
                    )
                )


                st.plotly_chart(
                    product_fig,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

                st.caption(
                    f"Date range: {range_start:%d %b %Y} to "
                    f"{range_end:%d %b %Y} | Geography: {geo} | "
                    f"Category: {category}"
                )

                with st.expander("View detailed product figures"):
                    st.dataframe(
                        product_summary[
                            ["Product_Name", "Value"]
                        ].rename(columns={
                            "Product_Name": "Product",
                            "Value": product_metric,
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

# ==========================================================
# END OF SECTIONS 9 & 10
# SECTION 11: ACTIONABLE ALERT FEED STARTS BELOW
# ==========================================================


# ==========================================================
# ADDITIONAL SECTION: CATEGORY KPI COMPARISON
# Uses existing date and geography filters
# ==========================================================

st.subheader("Category KPI Comparison")

st.caption(
    "Compare category performance over the selected date range "
    "against historical weekday expectations."
)

category_kpi_extra = st.selectbox(
    "Select KPI for Category Comparison",
    [
        "Orders",
        "Revenue (INR)",
        "Average Order Value (AOV)",
        "Cancellation Rate (%)",
    ],
    key="additional_category_kpi_selector",
)

extra_config = {
    "Orders": {
        "actual_col": "Orders",
        "daily_col": "Orders",
        "kind": "sum",
        "format": "{:,.0f}",
        "bad_direction": "lower",
    },
    "Revenue (INR)": {
        "actual_col": "Revenue_INR",
        "daily_col": "Revenue_INR",
        "kind": "sum",
        "format": "₹{:,.0f}",
        "bad_direction": "lower",
    },
    "Average Order Value (AOV)": {
        "actual_col": "AOV_INR",
        "daily_col": "AOV_INR",
        "kind": "ratio",
        "format": "₹{:,.2f}",
        "bad_direction": "lower",
    },
    "Cancellation Rate (%)": {
        "actual_col": "Cancellation_Rate_Pct",
        "daily_col": "Cancellation_Rate_Pct",
        "kind": "rate",
        "format": "{:.2f}%",
        "bad_direction": "higher",
    },
}

cfg = extra_config[category_kpi_extra]

if selected_data.empty or history_data.empty:
    st.info("No data is available for the selected date range.")

elif cfg["actual_col"] not in history_data.columns:
    st.error(
        f"Required column '{cfg['actual_col']}' is missing."
    )

else:
    extra_hist = history_data.copy()
    extra_selected = selected_data.copy()

    for frame in [extra_hist, extra_selected]:
        frame["Date"] = pd.to_datetime(
            frame["Date"], errors="coerce"
        )

        for col in [
            "Orders",
            "Revenue_INR",
            "AOV_INR",
            "Cancellation_Rate_Pct",
        ]:
            if col in frame.columns:
                frame[col] = pd.to_numeric(
                    frame[col], errors="coerce"
                )

        frame.dropna(
            subset=["Date", "Category"], inplace=True
        )

    # ------------------------------------------------------
    # ACTUAL VALUES OVER THE SELECTED DATE RANGE
    # ------------------------------------------------------

    actual_rows = []

    for cat, group in extra_selected.groupby("Category"):
        orders = group["Orders"].sum()
        revenue = group["Revenue_INR"].sum()

        if category_kpi_extra == "Orders":
            actual_value = orders

        elif category_kpi_extra == "Revenue (INR)":
            actual_value = revenue

        elif category_kpi_extra == "Average Order Value (AOV)":
            actual_value = (
                revenue / orders
                if orders > 0
                else float("nan")
            )

        else:
            weights = group["Orders"].clip(
                lower=0
            ).fillna(0)

            valid = group["Cancellation_Rate_Pct"].notna()
            valid_weights = weights[valid]
            valid_rates = group.loc[
                valid, "Cancellation_Rate_Pct"
            ]

            actual_value = (
                (valid_rates * valid_weights).sum()
                / valid_weights.sum()
                if valid_weights.sum() > 0
                else float("nan")
            )

        actual_rows.append({
            "Category": cat,
            "Actual": actual_value,
        })

    actual_df = pd.DataFrame(actual_rows)

    # ------------------------------------------------------
    # HISTORICAL DAILY KPI BY CATEGORY
    # ------------------------------------------------------

    daily_rows = []

    for (day, cat), group in extra_hist.groupby(
        [extra_hist["Date"].dt.normalize(), "Category"]
    ):
        orders = group["Orders"].sum()
        revenue = group["Revenue_INR"].sum()

        if category_kpi_extra == "Orders":
            value = orders

        elif category_kpi_extra == "Revenue (INR)":
            value = revenue

        elif category_kpi_extra == "Average Order Value (AOV)":
            value = (
                revenue / orders
                if orders > 0
                else float("nan")
            )

        else:
            weights = group["Orders"].clip(
                lower=0
            ).fillna(0)

            valid = group["Cancellation_Rate_Pct"].notna()
            valid_weights = weights[valid]
            valid_rates = group.loc[
                valid, "Cancellation_Rate_Pct"
            ]

            value = (
                (valid_rates * valid_weights).sum()
                / valid_weights.sum()
                if valid_weights.sum() > 0
                else float("nan")
            )

        daily_rows.append({
            "Date": pd.Timestamp(day),
            "Category": cat,
            "Daily_Value": value,
        })

    daily_df = pd.DataFrame(daily_rows)

    if daily_df.empty:
        st.info("No historical category data is available.")

    else:
        daily_df["Weekday"] = daily_df["Date"].dt.dayofweek

        # Same-weekday historical median for each category.
        weekday_baseline = (
            daily_df.groupby(
                ["Category", "Weekday"]
            )["Daily_Value"]
            .median()
            .rename("Weekday_Expected")
            .reset_index()
        )

        # Build the selected date range using the existing filters.
        range_start_extra = pd.to_datetime(
            extra_selected["Date"].min()
        ).normalize()

        range_end_extra = pd.to_datetime(
            extra_selected["Date"].max()
        ).normalize()

        expected_dates = pd.DataFrame({
            "Date": pd.date_range(
                range_start_extra,
                range_end_extra,
                freq="D",
            )
        })

        expected_dates["Weekday"] = (
            expected_dates["Date"].dt.dayofweek
        )

        category_names = sorted(
            extra_hist["Category"].dropna().unique()
        )

        expected_dates["_key"] = 1
        category_frame = pd.DataFrame({
            "Category": category_names,
            "_key": 1,
        })

        expected_grid = expected_dates.merge(
            category_frame, on="_key"
        ).drop(columns="_key")

        expected_grid = expected_grid.merge(
            weekday_baseline,
            on=["Category", "Weekday"],
            how="left",
        )

        # Sum expected daily counts/revenue.
        # Average expected daily AOV/cancellation rate.
        if cfg["kind"] == "sum":
            expected_df = (
                expected_grid.groupby(
                    "Category", as_index=False
                )
                .agg(
                    Expected=(
                        "Weekday_Expected",
                        lambda s: s.sum(min_count=1),
                    )
                )
            )
        else:
            expected_df = (
                expected_grid.groupby(
                    "Category", as_index=False
                )
                .agg(
                    Expected=("Weekday_Expected", "mean")
                )
            )

        # --------------------------------------------------
        # DEVIATION AND DISPLAY
        # --------------------------------------------------

        results = actual_df.merge(
            expected_df,
            on="Category",
            how="outer",
        )

        results["Deviation_Pct"] = (
            (results["Actual"] - results["Expected"])
            / results["Expected"].where(
                results["Expected"] != 0
            )
            * 100
        )

        if cfg["bad_direction"] == "higher":
            results["Unfavourable"] = (
                results["Deviation_Pct"] > 0
            )
        else:
            results["Unfavourable"] = (
                results["Deviation_Pct"] < 0
            )

        results["Status"] = results.apply(
            lambda row: (
                "Unfavourable"
                if pd.notna(row["Deviation_Pct"])
                and bool(row["Unfavourable"])
                else "Favourable"
                if pd.notna(row["Deviation_Pct"])
                else "Baseline unavailable"
            ),
            axis=1,
        )

        results = results.sort_values(
            "Actual", ascending=True, na_position="first"
        )

        results["Deviation_Label"] = results[
            "Deviation_Pct"
        ].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
        )

        results["Actual_Label"] = results["Actual"].apply(
            lambda x: cfg["format"].format(x)
            if pd.notna(x) else "N/A"
        )

        results["Expected_Label"] = results["Expected"].apply(
            lambda x: cfg["format"].format(x)
            if pd.notna(x) else "N/A"
        )

        results["Bar_Color"] = results["Status"].map({
            "Unfavourable": "#E74C3C",
            "Favourable": "#15966A",
            "Baseline unavailable": "#94A3B8",
        })

        st.markdown(
            f"**{category_kpi_extra} by Product Category**"
        )

        st.caption(
            f"Date range: {range_start_extra:%d %b %Y} – "
            f"{range_end_extra:%d %b %Y}"
        )

        # Native Plotly horizontal bar chart.
        # Values are actual KPI values; hover shows expected and deviation.
        import plotly.graph_objects as go

        fig_extra = go.Figure()

        for status in [
            "Unfavourable",
            "Favourable",
            "Baseline unavailable",
        ]:
            part = results[results["Status"] == status]

            if part.empty:
                continue

            fig_extra.add_trace(
                go.Bar(
                    x=part["Actual"],
                    y=part["Category"],
                    orientation="h",
                    name=status,
                    marker_color=part["Bar_Color"],
                    text=part["Actual_Label"],
                    textposition="outside",
                    cliponaxis=False,
                    customdata=part[
                        [
                            "Expected_Label",
                            "Deviation_Label",
                        ]
                    ].to_numpy(),
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Actual: %{text}<br>"
                        "Expected: %{customdata[0]}<br>"
                        "Deviation: %{customdata[1]}"
                        "<extra></extra>"
                    ),
                )
            )

        fig_extra.update_layout(
            barmode="overlay",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            height=max(300, 48 * len(results) + 90),
            margin=dict(l=5, r=65, t=10, b=35),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                x=0,
            ),
            xaxis=dict(
                title=f"Actual {category_kpi_extra}",
                showgrid=True,
                gridcolor="#E8EDF3",
                zeroline=False,
            ),
            yaxis=dict(
                title="",
                showgrid=False,
                automargin=True,
            ),
        )

        st.plotly_chart(
            fig_extra,
            use_container_width=True,
            config={"displayModeBar": False},
        )

        # Compact detail table with deviation percentages.
        with st.expander("View actual, expected and deviation by category"):
            detail_df = results[
                [
                    "Category",
                    "Actual_Label",
                    "Expected_Label",
                    "Deviation_Label",
                    "Status",
                ]
            ].rename(columns={
                "Actual_Label": "Actual",
                "Expected_Label": "Expected",
                "Deviation_Label": "Deviation vs Expected",
            })

            st.dataframe(
                detail_df,
                use_container_width=True,
                hide_index=True,
            )

        st.caption(
            "Red indicates an unfavourable change; green indicates "
            "a favourable change. Cancellation-rate increases are "
            "unfavourable. Baselines use the historical median for "
            "the same weekday. These are investigation signals, "
            "not confirmed root causes."
        )

# ==========================================================
# END OF ADDITIONAL CATEGORY KPI COMPARISON
# SECTION 11 CONTINUES BELOW
# ==========================================================

# ==================================================
# 11. ACTIONABLE ALERT FEED WITH CATEGORY & PRODUCTS
# ==================================================
st.subheader("Actionable Alert Feed")

if not alert_data.empty:
    # Sort alerts with the latest date first
    feed = alert_data.sort_values(
        "Date", ascending=False
    ).copy()

    # Build category and product details for each alert date
    category_details = []

    for alert_date in feed["Date"]:
        day_products = products[
            products["Date"].dt.date == alert_date.date()
        ].copy()

        # Apply selected geography filter
        if geo != "All" and "Geography" in day_products.columns:
            day_products = day_products[
                day_products["Geography"].astype(str) == geo
            ]

        # Apply selected category filter
        if category != "All" and "Category" in day_products.columns:
            day_products = day_products[
                day_products["Category"].astype(str) == category
            ]

        if day_products.empty:
            category_details.append({
                "Category": "No matching product data",
                "Products in Category": "N/A"
            })
            continue

        summaries = []

        for cat, group in day_products.groupby("Category"):
            product_totals = (
                group.groupby("Product_Name")["Orders"]
                .sum()
                .sort_values(ascending=False)
            )

            # Show the top five products by order volume
            product_names = ", ".join(
                product_totals.head(5).index.astype(str)
            )

            summaries.append(f"{cat}: {product_names}")

        category_details.append({
            "Category": "; ".join(
                sorted(
                    day_products["Category"]
                    .dropna()
                    .astype(str)
                    .unique()
                )
            ),
            "Products in Category": " | ".join(summaries)
        })

    # Attach category and product details to each alert
    details_df = pd.DataFrame(
        category_details,
        index=feed.index
    )

    feed = pd.concat([feed, details_df], axis=1)

    # Arrange the columns in the desired order
    preferred_order = [
        "Date",
        "Display_Priority",
        "Overall_Anomaly_Severity",
        "Category",
        "Products in Category",
        "Affected_KPI_Count",
        "Owner",
        "Supporting_Owner",
        "Recommended_Action"
    ]

    visible_columns = [
        col for col in preferred_order
        if col in feed.columns
    ]

    # Format date for display
    feed["Date"] = feed["Date"].dt.strftime("%Y-%m-%d")

    # Convert the table to HTML
    display_feed = feed[visible_columns].copy()

    html_table = display_feed.to_html(
        index=False,
        escape=True,
        classes="alert-table"
    )

    # CSS: wrap only Category, Products and Recommended Action
    st.markdown(
        """
        <style>
        .alert-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: auto;
            font-size: 13px;
        }

        .alert-table th,
        .alert-table td {
            border: 1px solid #d9dee7;
            padding: 9px;
            text-align: left;
            vertical-align: top;
            line-height: 1.5;
            white-space: nowrap;
            word-break: normal;
            overflow-wrap: normal;
        }

        .alert-table th {
            background-color: #FFFFFF;
            font-weight: 600;
        }

        /* Category: allow wrapping */
        .alert-table th:nth-child(4),
        .alert-table td:nth-child(4) {
            white-space: normal;
            overflow-wrap: break-word;
            min-width: 180px;
            max-width: 240px;
        }

        /* Products within Category: allow wrapping */
        .alert-table th:nth-child(5),
        .alert-table td:nth-child(5) {
            white-space: normal;
            overflow-wrap: anywhere;
            min-width: 220px;
            max-width: 320px;
        }

        /* Recommended Action: allow wrapping */
        .alert-table th:last-child,
        .alert-table td:last-child {
            white-space: normal;
            overflow-wrap: anywhere;
            min-width: 220px;
            max-width: 300px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Display the styled alert feed
    st.markdown(
        html_table,
        unsafe_allow_html=True
    )

    st.caption(
        "Products shown are the top five by order volume within each "
        "category for the alert date. These details support investigation "
        "but do not prove the cause of an anomaly."
    )

else:
    st.info(
        "No alerts match the selected date and priority filters."
    )


# ==================================================
# GEMINI AI NARRATIVE FUNCTION
# ==================================================
def generate_gemini_narrative(
    selected_row,
    affected,
    hypothesis,
    confidence,
    evidence,
    owner,
    supporting_owner,
    recommended_action
):
    """Generate an AI investigation narrative using Gemini."""

    from google import genai
    import streamlit as st

    api_key = st.secrets.get("GEMINI_API_KEY", "")
    model_name = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        return None, "GEMINI_API_KEY is missing from Streamlit Secrets."

    date_value = selected_row.get("Date", "Unknown")
    if hasattr(date_value, "strftime"):
        date_value = date_value.strftime("%Y-%m-%d")

    evidence_text = "\n".join(
        "- " + str(item) for item in evidence
    ) if evidence else "No detailed evidence supplied."

    prompt = f"""
You are an e-commerce anomaly investigation analyst.

Analyze this alert using only the supplied evidence.
Do not invent facts. Root causes must remain hypotheses,
not confirmed findings.

Date: {date_value}
Severity: {selected_row.get('Overall_Anomaly_Severity', 'Unknown')}
Affected KPIs: {affected}
Rule-based hypothesis: {hypothesis}
Rule-based confidence: {confidence}

Evidence:
{evidence_text}

Owner: {owner}
Supporting Owner: {supporting_owner}
Existing recommended action: {recommended_action}

Write a concise business-friendly report with these headings:

1. Alert Summary
2. Business Impact
3. Possible Root Causes
4. Evidence and Limitations
5. Three Prioritized Investigation Steps
6. Ownership and Recommended Action

Clearly separate observed evidence from possible explanations.
Do not claim a cause is confirmed unless the evidence proves it.
Preserve the assigned Owner and Supporting Owner.
"""

    try:
        client = genai.Client(api_key=api_key)

        response = client.interactions.create(
            model=model_name,
            input=prompt
        )

        narrative = (
            getattr(response, "output_text", None) or ""
        ).strip()

        if narrative:
            return narrative, None

        return None, "Gemini returned an empty response."

    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:400]}"

# ==================================================
# 12. ALERT INVESTIGATION: RULE-BASED + GEMINI
# ==================================================
st.subheader("Alert Investigation & Narrative")

if not alert_data.empty:
    choices = alert_data.sort_values("Date", ascending=False).copy()
    choices["Date_Label"] = choices["Date"].dt.strftime("%Y-%m-%d")

    selected_date = st.selectbox(
        "Select an alert date",
        choices["Date_Label"].tolist(),
        key="investigation_alert_date"
    )

    selected_row = choices[
        choices["Date_Label"] == selected_date
    ].iloc[0]

    affected, hypothesis, confidence, evidence = build_narrative(
        selected_row
    )

    st.markdown(
        f"### {selected_row.get('Overall_Anomaly_Severity', 'Unknown')} "
        f"alert — {selected_date}"
    )

    st.write("**Affected KPIs:**", affected)
    st.write("**Rule-based root-cause hypothesis:**", hypothesis)
    st.write("**Rule-based confidence:**", confidence)

    with st.expander("Evidence from detected metrics", expanded=True):
        if evidence:
            for item in evidence:
                st.write("•", item)
        else:
            st.write("No KPI deviation evidence is available for this alert.")

    owner = selected_row.get("Owner", "Not assigned")
    supporting_owner = selected_row.get(
        "Supporting_Owner", "Not assigned"
    )
    recommended_action = selected_row.get(
        "Recommended_Action",
        "Investigate the affected KPI and validate the evidence."
    )

    st.write("**Owner:**", owner)
    st.write("**Supporting Owner:**", supporting_owner)
    st.write("**Rule-based recommended action:**", recommended_action)

    st.caption(
        "The rule-based investigation is generated from dashboard rules. "
        "Its root-cause explanation is a hypothesis, not a confirmed finding."
    )

    st.divider()
    st.markdown("### ✨ Gemini AI Investigation Narrative")
    st.write(
        "Generate an AI-written investigation using the selected alert's "
        "KPI evidence, existing hypothesis and assigned ownership."
    )

    if st.button(
        "Generate Gemini Narrative",
        type="primary",
        key="generate_gemini_narrative"
    ):
        with st.spinner("Gemini is analyzing the selected alert evidence..."):
            gemini_text, gemini_error = generate_gemini_narrative(
                selected_row=selected_row,
                affected=affected,
                hypothesis=hypothesis,
                confidence=confidence,
                evidence=evidence,
                owner=owner,
                supporting_owner=supporting_owner,
                recommended_action=recommended_action
            )

        if gemini_text:
            st.session_state["gemini_narrative_date"] = selected_date
            st.session_state["gemini_narrative_text"] = gemini_text
            st.session_state["gemini_narrative_error"] = None
        else:
            st.session_state["gemini_narrative_date"] = selected_date
            st.session_state["gemini_narrative_text"] = None
            st.session_state["gemini_narrative_error"] = gemini_error

    if st.session_state.get("gemini_narrative_date") == selected_date:
        saved_narrative = st.session_state.get("gemini_narrative_text")
        saved_error = st.session_state.get("gemini_narrative_error")

        if saved_narrative:
            st.success("Generated successfully by Gemini")
            st.markdown(saved_narrative)
            st.caption(
                f"Model: {st.secrets.get('GEMINI_MODEL', 'gemini-3.8-flash')}. "
                "AI-generated analysis is advisory; validate hypotheses "
                "before taking action."
            )
        elif saved_error:
            st.error("Gemini could not generate a narrative.")
            st.code(saved_error)
            st.info(
                "Your rule-based narrative remains available above. "
                "Check the Gemini API key, model access, quota and app logs."
            )

else:
    st.info(
        "No alert is available for the selected date range and priority. "
        "Adjust the filters to view alerts."
    )

# ==================================================
# 13. FOOTER
# ==================================================
st.divider()
st.caption(
    "E-Commerce Anomaly Intelligence | Historical data | "
    "Statistical anomaly signals + evidence-led investigation + ownership"
)
