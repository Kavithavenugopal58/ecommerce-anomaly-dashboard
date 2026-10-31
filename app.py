
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

st.markdown(
    """
    <style>
    .ecom-header {
        background: linear-gradient(110deg, #17365D, #245B86);
        padding: 30px 26px 24px 26px;
        border-radius: 12px;
        margin: 8px 0 12px 0;
        box-sizing: border-box;
        overflow: visible;
    }

    .ecom-header-title {
        color: #FFFFFF !important;
        font-family: Arial, sans-serif !important;
        font-size: 32px !important;
        font-weight: 800 !important;
        line-height: 1.4 !important;
        margin: 0 0 12px 0 !important;
        padding: 0 !important;
        display: block !important;
    }

    .ecom-header-subtitle {
        color: #FFFFFF !important;
        font-family: Arial, sans-serif !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        line-height: 1.5 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
    }
    </style>

    <div class="ecom-header">
        <div class="ecom-header-title">
            E-Commerce Anomaly Intelligence
        </div>
        <div class="ecom-header-subtitle">
            Sales monitoring | Root-cause investigation | Action ownership
        </div>
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

    # Keep the two trend controls side by side for a cleaner layout.
    trend_filter_col1, trend_filter_col2 = st.columns(2)
    with trend_filter_col1:
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

    with trend_filter_col2:
        chart_view = st.selectbox(
            "Chart View",
            ["Overall Trend", "Category-wise Trend"],
            key="trend_chart_view_selector"
        )

    fig = go.Figure()

    # --------------------------------------------------
    # VIEW 1: OVERALL TREND
    # This retains the original overall detector chart.
    # --------------------------------------------------
    if chart_view == "Overall Trend":
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
    # VIEW 2: CATEGORY-WISE TREND
    # Plot every category as a separate line. The sidebar
    # Category filter is intentionally not applied here,
    # because this view must compare all categories.
    # Geography and date-range filters are still respected.
    # --------------------------------------------------
    else:
        category_history = products.copy()
        category_history["Date"] = pd.to_datetime(
            category_history["Date"], errors="coerce"
        )
        category_history = category_history.dropna(
            subset=["Date", "Category"]
        )

        range_start = pd.to_datetime(start_date).normalize()
        range_end = pd.to_datetime(end_date).normalize()

        category_history = category_history[
            (category_history["Date"] >= range_start)
            & (
                category_history["Date"]
                < range_end + pd.Timedelta(days=1)
            )
        ].copy()

        if geo != "All" and "Geography" in category_history.columns:
            category_history = category_history[
                category_history["Geography"].astype(str) == str(geo)
            ].copy()

        required_trend_cols = [
            "Category", "Orders", "Revenue_INR",
            "Cancellation_Rate_Pct"
        ]
        missing_trend_cols = [
            col for col in required_trend_cols
            if col not in category_history.columns
        ]

        if missing_trend_cols:
            st.warning(
                "Category-wise chart is missing these columns in "
                "product_data.csv: " + ", ".join(missing_trend_cols)
            )
        elif category_history.empty:
            st.info(
                "No category data is available for the selected "
                "date range and geography."
            )
        else:
            for col in [
                "Orders", "Revenue_INR", "Cancellation_Rate_Pct"
            ]:
                category_history[col] = pd.to_numeric(
                    category_history[col], errors="coerce"
                )

            # Aggregate product rows into one daily record per category.
            daily_category = (
                category_history.groupby(
                    ["Date", "Category"], as_index=False
                )
                .agg(
                    Orders=("Orders", "sum"),
                    Revenue_INR=("Revenue_INR", "sum")
                )
            )

            # Weighted cancellation rate at category/day level.
            category_history["_Cancel_Weighted"] = (
                category_history["Cancellation_Rate_Pct"]
                * category_history["Orders"].clip(lower=0)
            )
            cancel_daily = (
                category_history.groupby(
                    ["Date", "Category"], as_index=False
                )
                .agg(
                    Cancel_Weighted=("_Cancel_Weighted", "sum"),
                    Cancel_Orders=("Orders", "sum"),
                    Cancel_Mean=("Cancellation_Rate_Pct", "mean")
                )
            )
            cancel_daily["Cancellation Rate (%)"] = (
                cancel_daily["Cancel_Weighted"]
                / cancel_daily["Cancel_Orders"].where(
                    cancel_daily["Cancel_Orders"] > 0
                )
            )
            cancel_daily["Cancellation Rate (%)"] = (
                cancel_daily["Cancellation Rate (%)"].fillna(
                    cancel_daily["Cancel_Mean"]
                )
            )

            daily_category = daily_category.merge(
                cancel_daily[
                    ["Date", "Category", "Cancellation Rate (%)"]
                ],
                on=["Date", "Category"],
                how="left"
            )

            daily_category["Weighted AOV (INR)"] = (
                daily_category["Revenue_INR"]
                / daily_category["Orders"].where(
                    daily_category["Orders"] > 0
                )
            )

            metric_columns = {
                "Orders": "Orders",
                "Revenue (INR)": "Revenue_INR",
                "Weighted AOV (INR)": "Weighted AOV (INR)",
                "Cancellation Rate (%)": "Cancellation Rate (%)"
            }
            metric_col = metric_columns[kpi_name]

            daily_category = daily_category.sort_values(
                ["Category", "Date"]
            )

            categories_to_plot = sorted(
                daily_category["Category"].dropna().astype(str).unique()
            )
            palette = (
                px.colors.qualitative.Plotly
                + px.colors.qualitative.Dark24
                + px.colors.qualitative.Set3
            )

            for category_index, category_name in enumerate(categories_to_plot):
                category_daily = daily_category[
                    daily_category["Category"].astype(str) == category_name
                ].copy().sort_values("Date")

                category_daily[metric_col] = pd.to_numeric(
                    category_daily[metric_col], errors="coerce"
                )
                category_daily["Day_of_Week"] = (
                    category_daily["Date"].dt.dayofweek
                )

                # Calculate a leave-one-out weekday median baseline.
                # The current date is excluded from its own baseline.
                category_daily["Expected"] = float("nan")
                category_daily["MAD"] = float("nan")

                for row_idx in category_daily.index:
                    weekday = category_daily.loc[
                        row_idx, "Day_of_Week"
                    ]
                    reference = category_daily.loc[
                        (category_daily["Day_of_Week"] == weekday)
                        & (category_daily.index != row_idx),
                        metric_col
                    ].dropna()

                    if len(reference) < 2:
                        reference = category_daily.loc[
                            category_daily.index != row_idx,
                            metric_col
                        ].dropna()

                    if not reference.empty:
                        expected_value = reference.median()
                        mad_value = (
                            reference - expected_value
                        ).abs().median()
                        category_daily.loc[row_idx, "Expected"] = expected_value
                        category_daily.loc[row_idx, "MAD"] = mad_value

                deviation = (
                    category_daily[metric_col]
                    - category_daily["Expected"]
                ).abs()

                metric_median = category_daily[metric_col].median()
                metric_scale = max(
                    abs(float(metric_median))
                    if pd.notna(metric_median) else 0.0,
                    1.0
                )
                tolerance = metric_scale * 0.01

                category_daily["Is_Anomaly"] = (
                    category_daily["Expected"].notna()
                    & category_daily["MAD"].notna()
                    & (
                        (
                            (category_daily["MAD"] > 0)
                            & (deviation > 3 * category_daily["MAD"])
                        )
                        | (
                            (category_daily["MAD"] == 0)
                            & (deviation > tolerance)
                        )
                    )
                )

                line_color = palette[
                    category_index % len(palette)
                ]

                fig.add_trace(go.Scatter(
                    x=category_daily["Date"],
                    y=category_daily[metric_col],
                    mode="lines+markers",
                    name=category_name,
                    line=dict(color=line_color, width=2),
                    marker=dict(size=4, color=line_color),
                    connectgaps=False,
                    customdata=category_daily[
                        ["Expected", "MAD"]
                    ].to_numpy(),
                    hovertemplate=(
                        "<b>" + category_name + "</b><br>"
                        "%{x|%d %b %Y}<br>"
                        + kpi_name + ": %{y:,.2f}<br>"
                        "Expected: %{customdata[0]:,.2f}"
                        "<extra></extra>"
                    )
                ))

                anomaly_data = category_daily[
                    category_daily["Is_Anomaly"].fillna(False)
                ].dropna(subset=[metric_col])

                if not anomaly_data.empty:
                    fig.add_trace(go.Scatter(
                        x=anomaly_data["Date"],
                        y=anomaly_data[metric_col],
                        mode="markers",
                        name=f"{category_name} anomaly",
                        showlegend=False,
                        marker=dict(
                            color="#FF3B30",
                            size=10,
                            symbol="circle",
                            line=dict(color="#FFFFFF", width=1)
                        ),
                        customdata=anomaly_data[
                            ["Expected", "MAD"]
                        ].to_numpy(),
                        hovertemplate=(
                            "<b>Anomaly — " + category_name + "</b><br>"
                            "%{x|%d %b %Y}<br>"
                            + kpi_name + ": %{y:,.2f}<br>"
                            "Expected: %{customdata[0]:,.2f}"
                            "<extra></extra>"
                        )
                    ))

            st.caption(
                "Each coloured line represents one product category. "
                "Red markers identify potential category-level anomalies. "
                "These are exploratory category signals calculated from "
                "product_data.csv; they are not the original overall "
                "detector's alerts. The chart includes all categories, "
                "regardless of the sidebar Category filter."
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

    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF"
    )
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

        category_filter_col1, category_filter_col2 = st.columns(2)
        with category_filter_col1:
            category_kpi = st.selectbox(
                "Select KPI for Category Investigation",
                list(KPI_CONFIG.keys()),
                key="category_investigation_kpi",
            )
        with category_filter_col2:
            category_view = st.selectbox(
                "Category View",
                ["Category Contribution (%)", "Actual vs Expected by Category"],
                key="category_investigation_view",
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

            # --------------------------------------------------
            # DISPLAY SELECTED CATEGORY VIEW
            # --------------------------------------------------
            if category_view == "Category Contribution (%)":
                # Orders and revenue are additive, so category share is
                # a meaningful percentage of the overall total.
                if category_kpi in ["Orders", "Revenue (INR)"]:
                    contribution_total = results["Actual"].clip(lower=0).sum()
                    results["Category_Share_Pct"] = (
                        results["Actual"].clip(lower=0) / contribution_total * 100
                        if contribution_total > 0 else 0.0
                    )
                    contribution_data = results.dropna(
                        subset=["Category_Share_Pct"]
                    ).sort_values("Category_Share_Pct", ascending=True)

                    st.markdown(
                        f"**{cfg['label']} — percentage contribution by category**"
                    )
                    if contribution_data.empty or contribution_total <= 0:
                        st.info("No positive category values are available for this selection.")
                    else:
                        contribution_fig = px.bar(
                            contribution_data,
                            x="Category_Share_Pct",
                            y="Category",
                            orientation="h",
                            text=contribution_data["Category_Share_Pct"].map(
                                lambda value: f"{value:.1f}%"
                            ),
                            labels={
                                "Category_Share_Pct": "Share of total (%)",
                                "Category": "",
                            },
                        )
                        contribution_fig.update_traces(
                            marker_color="#2878D0",
                            textposition="outside",
                            cliponaxis=False,
                            hovertemplate=(
                                "<b>%{y}</b><br>Share: %{x:.1f}%<extra></extra>"
                            ),
                        )
                        contribution_fig.update_layout(
                            paper_bgcolor="#FFFFFF",
                            plot_bgcolor="#FFFFFF",
                            height=360,
                            margin=dict(l=12, r=45, t=20, b=35),
                            xaxis=dict(
                                title="Share of total (%)",
                                ticksuffix="%",
                                range=[0, max(100, contribution_data["Category_Share_Pct"].max() * 1.15)],
                                gridcolor="#E2E8F0",
                            ),
                            yaxis=dict(title=None, automargin=True),
                            showlegend=False,
                        )
                        st.plotly_chart(
                            contribution_fig,
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )
                        with st.expander("View category contribution figures"):
                            share_table = contribution_data[
                                ["Category", "Actual", "Category_Share_Pct"]
                            ].sort_values("Category_Share_Pct", ascending=False).rename(
                                columns={
                                    "Actual": f"Total {cfg['label']}",
                                    "Category_Share_Pct": "Share of Total (%)",
                                }
                            )
                            st.dataframe(share_table, use_container_width=True, hide_index=True)
                else:
                    # AOV and cancellation rate are ratios, not additive
                    # measures. Showing a share of their sum would mislead.
                    st.info(
                        "Category contribution percentages are meaningful for Orders and Revenue. "
                        "For AOV and Cancellation Rate, select 'Actual vs Expected by Category' "
                        "because these are rate-based KPIs and do not add up across categories."
                    )

            else:
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
                        font=dict(family="Arial, sans-serif", size=13, color="#263238"),
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.02, x=0,
                            font=dict(size=11, color="#263238"),
                        ),
                        xaxis=dict(
                            title=dict(text="Unfavourable difference", font=dict(size=12, color="#263238")),
                            tickfont=dict(size=11, color="#344054"),
                            gridcolor="#E2E8F0",
                            zerolinecolor="#94A3B8",
                            automargin=True,
                        ),
                        yaxis=dict(title=None, tickfont=dict(size=11, color="#344054"), automargin=True),
                    )
                    st.plotly_chart(
                        category_fig,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                    st.caption(
                        "Red indicates an unfavourable gap; green indicates better-than-expected "
                        "performance. For cancellation rate, an increase is unfavourable. "
                        "These signals support investigation and do not prove root cause."
                    )
                    with st.expander("View detailed category figures"):
                        detail_table = results[
                            ["Category", "Actual", "Expected", "Gap", "Contribution_Pct", "Status"]
                        ].rename(columns={
                            "Actual": f"Actual {cfg['label']}",
                            "Expected": f"Expected {cfg['label']}",
                            "Gap": "Unfavourable Gap",
                            "Contribution_Pct": "Share of Adverse Gap (%)",
                        })
                        st.dataframe(detail_table, use_container_width=True, hide_index=True)

    # ------------------------------------------------------
    # SECTION 10: PRODUCT-LEVEL INVESTIGATION
    # ------------------------------------------------------

    with product_col:
        st.subheader("Product-Level Investigation")

        st.caption(
            "Explore product contribution or identify products with "
            "potential KPI anomalies within the selected category."
        )

        product_filtered = selected_data.copy()

        if category != "All":
            product_filtered = product_filtered[
                product_filtered["Category"].astype(str) == str(category)
            ].copy()

        # Two modes: preserve the existing contribution pie and add
        # product-level anomaly investigation as a separate view.
        product_view_col1, product_view_col2 = st.columns(2)
        with product_view_col1:
            product_metric = st.selectbox(
                "Select KPI",
                list(KPI_CONFIG.keys()),
                key="product_investigation_metric",
            )
        with product_view_col2:
            product_view = st.selectbox(
                "Product View",
                ["Product Contribution (%)", "Product Anomaly Investigation"],
                key="product_investigation_view",
            )

        if product_filtered.empty:
            st.info(
                "No product data matches the selected dates, "
                "geography and category."
            )
        elif product_view == "Product Contribution (%)":
            # EXISTING VIEW — overall percentage contribution of each product.
            if product_metric == "Orders":
                product_summary = product_filtered.groupby(
                    "Product_Name", as_index=False
                ).agg(Value=("Orders", "sum"))

            elif product_metric == "Revenue (INR)":
                product_summary = product_filtered.groupby(
                    "Product_Name", as_index=False
                ).agg(Value=("Revenue_INR", "sum"))

            elif product_metric == "Average Order Value (AOV)":
                product_summary = product_filtered.groupby(
                    "Product_Name", as_index=False
                ).agg(
                    Revenue=("Revenue_INR", "sum"),
                    Orders=("Orders", "sum"),
                )
                product_summary["Value"] = (
                    product_summary["Revenue"]
                    / product_summary["Orders"].where(product_summary["Orders"] > 0)
                )

            else:
                product_filtered["_Cancel_Weighted"] = (
                    product_filtered["Cancellation_Rate_Pct"]
                    * product_filtered["Orders"].clip(lower=0)
                )
                product_summary = product_filtered.groupby(
                    "Product_Name", as_index=False
                ).agg(
                    Cancel_Weighted=("_Cancel_Weighted", "sum"),
                    Orders=("Orders", "sum"),
                )
                product_summary["Value"] = (
                    product_summary["Cancel_Weighted"]
                    / product_summary["Orders"].where(product_summary["Orders"] > 0)
                )

            product_summary = product_summary.dropna(subset=["Value"])
            product_summary = product_summary[product_summary["Value"] >= 0].sort_values(
                "Value", ascending=False
            )

            if product_summary.empty or product_summary["Value"].sum() <= 0:
                st.info("No positive values are available for this KPI under the selected filters.")
            else:
                top_n = 7
                if len(product_summary) > top_n:
                    product_chart_data = product_summary.head(top_n)[
                        ["Product_Name", "Value"]
                    ].copy()
                    other_value = product_summary.iloc[top_n:]["Value"].sum()
                    if other_value > 0:
                        product_chart_data = pd.concat(
                            [
                                product_chart_data,
                                pd.DataFrame({
                                    "Product_Name": ["Other products"],
                                    "Value": [other_value],
                                }),
                            ], ignore_index=True
                        )
                else:
                    product_chart_data = product_summary[["Product_Name", "Value"]].copy()

                product_fig = px.pie(
                    product_chart_data,
                    names="Product_Name",
                    values="Value",
                    hole=0.42,
                    title=f"{product_metric} by Product — Contribution",
                )
                product_fig.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    hovertemplate=(
                        "<b>%{label}</b><br>Value: %{value:,.2f}<br>"
                        "Share: %{percent}<extra></extra>"
                    ),
                )
                product_fig.update_layout(
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    height=360,
                    autosize=True,
                    margin=dict(l=12, r=12, t=45, b=55),
                    font=dict(family="Arial, sans-serif", size=13, color="#263238"),
                    title=dict(
                        text=f"{product_metric} by Product — Contribution",
                        font=dict(size=17, color="#172B4D"),
                        x=0.02, xanchor="left"
                    ),
                    legend=dict(
                        orientation="h", yanchor="top", y=-0.08,
                        x=0, font=dict(size=10, color="#263238")
                    )
                )
                st.plotly_chart(product_fig, use_container_width=True,
                                config={"displayModeBar": False})
                st.caption(
                    f"Date range: {range_start:%d %b %Y} to {range_end:%d %b %Y} | "
                    f"Geography: {geo} | Category: {category}. "
                    "Percentages show each product's share of the selected KPI."
                )
                with st.expander("View detailed product contribution"):
                    contribution_table = product_summary[["Product_Name", "Value"]].copy()
                    contribution_table["Contribution (%)"] = (
                        contribution_table["Value"] / contribution_table["Value"].sum() * 100
                    )
                    st.dataframe(
                        contribution_table.rename(columns={
                            "Product_Name": "Product", "Value": product_metric
                        }), use_container_width=True, hide_index=True
                    )

        else:
            # NEW VIEW — compare each product with its own weekday baseline.
            # Historical reference uses all available dates, while the
            # results displayed are limited to the selected date range.
            anomaly_history = history_data.copy()
            if category != "All":
                anomaly_history = anomaly_history[
                    anomaly_history["Category"].astype(str) == str(category)
                ].copy()

            if anomaly_history.empty:
                st.info("No historical product records are available for this category and geography.")
            else:
                # Aggregate to one daily record per product.
                anomaly_history["Orders"] = pd.to_numeric(anomaly_history["Orders"], errors="coerce")
                anomaly_history["Revenue_INR"] = pd.to_numeric(anomaly_history["Revenue_INR"], errors="coerce")
                anomaly_history["Cancellation_Rate_Pct"] = pd.to_numeric(
                    anomaly_history["Cancellation_Rate_Pct"], errors="coerce"
                )
                product_daily = anomaly_history.groupby(
                    ["Date", "Category", "Product_Name"], as_index=False
                ).agg(
                    Orders=("Orders", "sum"),
                    Revenue_INR=("Revenue_INR", "sum"),
                    Cancel_Weighted=("Cancellation_Rate_Pct", lambda x: 0.0),
                )

                anomaly_history["_Cancel_Weighted"] = (
                    anomaly_history["Cancellation_Rate_Pct"] * anomaly_history["Orders"].clip(lower=0)
                )
                cancel_product_daily = anomaly_history.groupby(
                    ["Date", "Category", "Product_Name"], as_index=False
                ).agg(
                    Cancel_Weighted=("_Cancel_Weighted", "sum"),
                    Cancel_Orders=("Orders", "sum"),
                    Cancel_Mean=("Cancellation_Rate_Pct", "mean"),
                )
                cancel_product_daily["Cancellation Rate (%)"] = (
                    cancel_product_daily["Cancel_Weighted"] /
                    cancel_product_daily["Cancel_Orders"].where(cancel_product_daily["Cancel_Orders"] > 0)
                ).fillna(cancel_product_daily["Cancel_Mean"])
                product_daily = product_daily.drop(columns=["Cancel_Weighted"]).merge(
                    cancel_product_daily[["Date", "Category", "Product_Name", "Cancellation Rate (%)"]],
                    on=["Date", "Category", "Product_Name"], how="left"
                )
                product_daily["Average Order Value (AOV)"] = (
                    product_daily["Revenue_INR"] /
                    product_daily["Orders"].where(product_daily["Orders"] > 0)
                )
                metric_col = {
                    "Orders": "Orders",
                    "Revenue (INR)": "Revenue_INR",
                    "Average Order Value (AOV)": "Average Order Value (AOV)",
                    "Cancellation Rate (%)": "Cancellation Rate (%)",
                }[product_metric]
                product_daily["Day_of_Week"] = product_daily["Date"].dt.dayofweek
                product_daily = product_daily.sort_values("Date").reset_index(drop=True)

                # Leave-one-out weekday median and MAD per product.
                product_daily["Expected"] = float("nan")
                product_daily["MAD"] = float("nan")
                for (cat_name, product_name), product_group in product_daily.groupby(
                    ["Category", "Product_Name"]
                ):
                    group_indices = product_group.index
                    for row_idx in group_indices:
                        weekday = product_daily.at[row_idx, "Day_of_Week"]
                        reference = product_daily.loc[
                            (product_daily.index.isin(group_indices)) &
                            (product_daily["Day_of_Week"] == weekday) &
                            (product_daily.index != row_idx), metric_col
                        ].dropna()
                        if len(reference) < 2:
                            reference = product_daily.loc[
                                product_daily.index.isin(group_indices) &
                                (product_daily.index != row_idx), metric_col
                            ].dropna()
                        if not reference.empty:
                            expected_value = reference.median()
                            product_daily.at[row_idx, "Expected"] = expected_value
                            product_daily.at[row_idx, "MAD"] = (reference - expected_value).abs().median()

                product_daily["Deviation"] = product_daily[metric_col] - product_daily["Expected"]
                product_daily["Abs_Deviation"] = product_daily["Deviation"].abs()
                # Adverse direction: falling orders/revenue/AOV or rising cancellation.
                if product_metric == "Cancellation Rate (%)":
                    product_daily["Adverse_Deviation"] = product_daily["Deviation"]
                else:
                    product_daily["Adverse_Deviation"] = -product_daily["Deviation"]
                product_daily["Deviation_Pct"] = (
                    product_daily["Adverse_Deviation"] /
                    product_daily["Expected"].abs().replace(0, pd.NA) * 100
                )
                product_daily["Threshold"] = 3 * product_daily["MAD"].fillna(0)
                product_daily["Tolerance"] = product_daily["Expected"].abs().fillna(0) * 0.01
                product_daily["Is_Anomaly"] = (
                    product_daily["Expected"].notna() &
                    product_daily["Adverse_Deviation"].gt(0) &
                    (
                        product_daily["Adverse_Deviation"].gt(product_daily["Threshold"]) |
                        ((product_daily["MAD"].fillna(0) == 0) &
                         product_daily["Adverse_Deviation"].gt(product_daily["Tolerance"]))
                    )
                )

                selected_product_daily = product_daily[
                    (product_daily["Date"] >= range_start) &
                    (product_daily["Date"] < range_end + pd.Timedelta(days=1))
                ].copy()
                anomaly_rows = selected_product_daily[
                    selected_product_daily["Is_Anomaly"].fillna(False)
                ].copy()

                if selected_product_daily.empty:
                    st.info("No product-level daily data exists in the selected period.")
                elif anomaly_rows.empty:
                    st.success(
                        "No product-level adverse anomalies were detected for this KPI "
                        "within the selected category, geography and date range."
                    )
                else:
                    product_impact = anomaly_rows.groupby("Product_Name", as_index=False).agg(
                        Anomaly_Days=("Date", "nunique"),
                        Worst_Adverse_Deviation_Pct=("Deviation_Pct", "max"),
                        Total_Adverse_Deviation=("Adverse_Deviation", "sum"),
                    ).sort_values(
                        ["Anomaly_Days", "Worst_Adverse_Deviation_Pct"], ascending=False
                    )
                    st.markdown("**Products with potential adverse anomalies**")
                    impact_fig = px.bar(
                        product_impact.head(10).sort_values("Worst_Adverse_Deviation_Pct"),
                        x="Worst_Adverse_Deviation_Pct",
                        y="Product_Name",
                        orientation="h",
                        color="Anomaly_Days",
                        color_continuous_scale="Reds",
                        hover_data={
                            "Anomaly_Days": True,
                            "Worst_Adverse_Deviation_Pct": ":.1f",
                            "Total_Adverse_Deviation": ":,.2f",
                        },
                        labels={
                            "Worst_Adverse_Deviation_Pct": "Worst adverse deviation (%)",
                            "Product_Name": "Product",
                            "Anomaly_Days": "Anomaly days",
                        },
                    )
                    impact_fig.update_layout(
                        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                        height=360, margin=dict(l=10, r=10, t=25, b=35),
                        font=dict(color="#263238", size=11),
                        coloraxis_colorbar=dict(title="Anomaly days"),
                    )
                    st.plotly_chart(impact_fig, use_container_width=True,
                                    config={"displayModeBar": False})
                    st.caption(
                        "Products are ranked by the number of adverse anomaly days and "
                        "the largest adverse deviation. For Orders, Revenue and AOV, "
                        "a drop is treated as adverse; for Cancellation Rate, an increase "
                        "is adverse. These are investigation signals, not proof of cause."
                    )
                    with st.expander("View product anomaly dates and evidence", expanded=True):
                        evidence_table = anomaly_rows[[
                            "Date", "Category", "Product_Name", metric_col,
                            "Expected", "Deviation_Pct", "MAD"
                        ]].rename(columns={
                            "Date": "Anomaly Date",
                            "Product_Name": "Product",
                            metric_col: f"Actual {product_metric}",
                            "Expected": "Expected Baseline",
                            "Deviation_Pct": "Adverse Deviation (%)",
                            "MAD": "Historical MAD",
                        }).sort_values("Adverse Deviation (%)", ascending=False)
                        st.dataframe(evidence_table, use_container_width=True, hide_index=True)


# ==========================================================
# END OF SECTIONS 9 & 10
# SECTION 11: ACTIONABLE ALERT FEED STARTS BELOW
# ==========================================================


# ==========================================================
# SECTION 11: ACTIONABLE ALERT FEED STARTS BELOW
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
    """Generate a Gemini investigation narrative grounded in Google Search."""

    from google import genai
    import streamlit as st
    from datetime import timedelta

    api_key = st.secrets.get("GEMINI_API_KEY", "")
    model_name = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        return None, [], "GEMINI_API_KEY is missing from Streamlit Secrets."

    date_value = selected_row.get("Date", "Unknown")
    if hasattr(date_value, "strftime"):
        alert_date = date_value.date() if hasattr(date_value, "date") else date_value
        date_text = alert_date.strftime("%Y-%m-%d")
        search_start = (alert_date - timedelta(days=3)).strftime("%Y-%m-%d")
        search_end = (alert_date + timedelta(days=3)).strftime("%Y-%m-%d")
    else:
        date_text = str(date_value)
        search_start = date_text
        search_end = date_text

    evidence_text = "\n".join(
        "- " + str(item) for item in evidence
    ) if evidence else "No detailed evidence supplied."

    prompt = f"""
You are an e-commerce anomaly investigation analyst for an India-focused
online retail business. Analyze the internal alert and research relevant
external e-commerce events using Google Search.

ALERT DATE: {date_text}
EXTERNAL EVENT SEARCH WINDOW: {search_start} to {search_end} (inclusive).
Search for events that OCCURRED during this window, not merely events that
are currently being advertised. Article publication date may differ from
the event date; clearly distinguish them.

Search broadly across relevant Indian e-commerce context, including Amazon
India, Flipkart and other major platforms, major sale/promotional campaigns,
shopping festivals, competitor events, logistics/last-mile disruptions,
fulfilment or payment outages, regulatory changes, and other credible
market events that could plausibly affect online retail KPIs.

Do not assume an event happened. Include only findings supported by the
search results. Prefer official company announcements and reputable news
sources. If no relevant event is found for this historical date window,
state: "No relevant external event was verified in the searched sources."
Do not substitute present-day 2026 promotions for events in the alert window.

INTERNAL ALERT EVIDENCE (treat this as the source of truth for dashboard metrics):
Date: {date_text}
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
3. Internal Evidence and Possible Root Causes
4. External Event Context (include event date, source publication date if
   available, relevance, and whether the connection is weak/moderate/strong)
5. Evidence Limitations
6. Three Prioritized Investigation Steps
7. Ownership and Recommended Action

Keep internal statistical evidence separate from external web findings.
An event occurring at the same time is NOT proof that it caused the anomaly.
Do not claim causation. If relevance is uncertain, say so. Preserve the
assigned Owner and Supporting Owner. Do not invent citations or sources;
Google Search citations will be displayed separately by the application.
"""

    try:
        client = genai.Client(api_key=api_key)

        # Google Search grounding lets Gemini search for dated events and
        # return URL citations with its answer.
        response = client.interactions.create(
            model=model_name,
            input=prompt,
            tools=[{"type": "google_search"}]
        )

        narrative = (getattr(response, "output_text", None) or "").strip()

        # Extract source citations from the Interactions API model-output steps.
        citations = []
        seen_urls = set()
        for step in (getattr(response, "steps", None) or []):
            if getattr(step, "type", None) != "model_output":
                continue
            for block in (getattr(step, "content", None) or []):
                for annotation in (getattr(block, "annotations", None) or []):
                    if getattr(annotation, "type", None) != "url_citation":
                        continue
                    url = (
                        getattr(annotation, "uri", None)
                        or getattr(annotation, "url", None)
                    )
                    title = getattr(annotation, "title", None) or url
                    if url and url not in seen_urls:
                        citations.append({"title": str(title), "url": str(url)})
                        seen_urls.add(url)

        if narrative:
            return narrative, citations, None

        return None, [], "Gemini returned an empty response."

    except Exception as exc:
        return None, [], f"{type(exc).__name__}: {str(exc)[:400]}"

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
        with st.spinner("Gemini is analyzing the alert and searching for relevant e-commerce events..."):
            gemini_text, gemini_citations, gemini_error = generate_gemini_narrative(
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
            st.session_state["gemini_narrative_citations"] = gemini_citations
            st.session_state["gemini_narrative_error"] = None
        else:
            st.session_state["gemini_narrative_date"] = selected_date
            st.session_state["gemini_narrative_text"] = None
            st.session_state["gemini_narrative_citations"] = []
            st.session_state["gemini_narrative_error"] = gemini_error

    if st.session_state.get("gemini_narrative_date") == selected_date:
        saved_narrative = st.session_state.get("gemini_narrative_text")
        saved_error = st.session_state.get("gemini_narrative_error")

        if saved_narrative:
            st.success("Generated successfully by Gemini")
            st.markdown(saved_narrative)
            saved_citations = st.session_state.get("gemini_narrative_citations", [])
            if saved_citations:
                with st.expander("External research sources (Google Search)", expanded=False):
                    for source in saved_citations:
                        st.markdown(f"- [{source['title']}]({source['url']})")
            else:
                st.caption(
                    "No URL citations were returned by Google Search for this narrative. "
                    "Treat any external-event summary as unverified until checked."
                )
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



# ==========================================================
# 12A. PDF INVESTIGATION REPORT GENERATOR
# ==========================================================
st.divider()
st.subheader("Investigation Report")
st.write(
    "Generate a downloadable PDF containing the selected-period KPI trends, "
    "category and product investigation, alert priorities, and available "
    "rule-based or Gemini narrative."
)

def build_investigation_pdf():
    """Build a multi-page PDF from the dashboard's current filters and data."""
    import io
    from datetime import datetime
    from xml.sax.saxutils import escape

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image as RLImage, KeepTogether
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="E-Commerce Anomaly Intelligence Investigation Report",
        author="E-Commerce Anomaly Intelligence"
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=19, leading=23,
        textColor=colors.HexColor("#17365D"), alignment=TA_CENTER,
        spaceAfter=5 * mm
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=styles["Heading2"],
        fontSize=13, leading=16, textColor=colors.HexColor("#17365D"),
        spaceBefore=4 * mm, spaceAfter=2 * mm
    ))
    styles.add(ParagraphStyle(
        name="SmallText", parent=styles["BodyText"],
        fontSize=8, leading=10
    ))
    styles.add(ParagraphStyle(
        name="NarrativeText", parent=styles["BodyText"],
        fontSize=9, leading=13, spaceAfter=2 * mm
    ))

    story = []
    report_date = datetime.now().strftime("%d %b %Y, %H:%M")
    story.append(Paragraph("E-Commerce Anomaly Intelligence", styles["ReportTitle"]))
    story.append(Paragraph(
        "Business Performance &amp; Anomaly Investigation Report",
        ParagraphStyle(
            "SubTitle", parent=styles["Normal"], alignment=TA_CENTER,
            fontSize=11, textColor=colors.HexColor("#526579")
        )
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"<b>Reporting period:</b> {escape(str(start_date))} to {escape(str(end_date))}"
        f" &nbsp;&nbsp; <b>Geography:</b> {escape(str(geo))}"
        f" &nbsp;&nbsp; <b>Category filter:</b> {escape(str(category))}",
        styles["SmallText"]
    ))
    story.append(Paragraph(
        f"<b>Generated:</b> {report_date} &nbsp;&nbsp; "
        "<b>Data basis:</b> Historical dashboard dataset",
        styles["SmallText"]
    ))

    def make_table(rows, widths=None, header=True, font_size=7):
        wrapped = []
        for row_index, row in enumerate(rows):
            wrapped_row = []
            for value in row:
                value_text = "—" if value is None or pd.isna(value) else str(value)
                wrapped_row.append(Paragraph(
                    escape(value_text).replace("\n", "<br/>"),
                    styles["SmallText"]
                ))
            wrapped.append(wrapped_row)
        if widths is None and rows and len(rows[0]) > 0:
            widths = [180 * mm / len(rows[0])] * len(rows[0])
        table = Table(wrapped, colWidths=widths, repeatRows=1 if header else 0,
                      hAlign="LEFT")
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DCE5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if header and rows:
            commands += [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0F6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365D")),
            ]
        table.setStyle(TableStyle(commands))
        return table

    # Executive summary and KPI cards
    story.append(Paragraph("1. Executive Summary", styles["SectionHeading"]))
    summary_rows = [
        ["Measure", "Selected-period result"],
        ["Total orders", f"{range_orders:,.0f}"],
        ["Total revenue", f"₹{range_revenue:,.2f}"],
        ["Weighted average order value", f"₹{range_aov:,.2f}"],
        ["Average daily cancellation rate", f"{range_cancellation:.2f}%"
         if pd.notna(range_cancellation) else "N/A"],
        ["Alerts in selected priority/date filters", str(len(alert_data))],
    ]
    story.append(make_table(summary_rows, widths=[75 * mm, 90 * mm]))
    story.append(Spacer(1, 2 * mm))

    # KPI trend table and charts
    story.append(Paragraph("2. KPI Trend Analysis", styles["SectionHeading"]))
    trend_cols = [
        ("Orders", "Total_Orders", "Total_Orders_Expected"),
        ("Revenue (INR)", "Total_Revenue_INR", "Total_Revenue_INR_Expected"),
        ("Weighted AOV (INR)", "Weighted_AOV_INR", "Weighted_AOV_INR_Expected"),
        ("Cancellation Rate (%)", "Avg_Cancellation_Rate_Pct",
         "Avg_Cancellation_Rate_Pct_Expected"),
    ]
    trend_table = [["KPI", "Actual (period)", "Expected (daily baseline avg)", "Days"]]
    for label, actual_col, expected_col in trend_cols:
        if actual_col in det.columns:
            actual_series = pd.to_numeric(det[actual_col], errors="coerce")
            if label == "Orders":
                actual_value = f"{actual_series.sum():,.0f}"
            elif label == "Revenue (INR)":
                actual_value = f"₹{actual_series.sum():,.2f}"
            elif label == "Weighted AOV (INR)":
                actual_value = f"₹{(range_aov):,.2f}"
            else:
                actual_value = f"{actual_series.mean():.2f}%"
            expected_value = (
                f"{pd.to_numeric(det[expected_col], errors='coerce').mean():,.2f}"
                if expected_col in det.columns else "Unavailable"
            )
            trend_table.append([label, actual_value, expected_value, str(actual_series.notna().sum())])
    story.append(make_table(trend_table, widths=[43 * mm, 43 * mm, 57 * mm, 22 * mm]))

    # Four KPI trend charts; each uses actual and expected values from detected.csv.
    for label, actual_col, expected_col in trend_cols:
        if actual_col not in det.columns:
            continue
        chart_df = det[["Date", actual_col]].copy()
        chart_df[actual_col] = pd.to_numeric(chart_df[actual_col], errors="coerce")
        if expected_col in det.columns:
            chart_df["Expected"] = pd.to_numeric(det[expected_col], errors="coerce")
        chart_df = chart_df.dropna(subset=[actual_col]).sort_values("Date")
        if chart_df.empty:
            continue
        fig, ax = plt.subplots(figsize=(7.0, 2.2))
        ax.plot(chart_df["Date"], chart_df[actual_col], label="Actual", linewidth=1.5)
        if "Expected" in chart_df.columns:
            ax.plot(chart_df["Date"], chart_df["Expected"], label="Expected baseline",
                    linestyle="--", linewidth=1.2)
        ax.set_title(label, fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
        fig.autofmt_xdate()
        fig.tight_layout()
        chart_buffer = io.BytesIO()
        fig.savefig(chart_buffer, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        chart_buffer.seek(0)
        story.append(RLImage(chart_buffer, width=165 * mm, height=52 * mm))
        story.append(Spacer(1, 1 * mm))

    # Alert priority distribution and alert table
    story.append(Paragraph("3. Alert Priorities", styles["SectionHeading"]))
    if not alert_data.empty:
        priority_counts = (
            alert_data["Display_Priority"].value_counts().to_dict()
            if "Display_Priority" in alert_data.columns else {}
        )
        priority_rows = [["Priority", "Alert count"]]
        for priority in ["P1 - Immediate", "P2 - High", "P3 - Watch", "P4 - Normal"]:
            priority_rows.append([priority, str(priority_counts.get(priority, 0))])
        story.append(make_table(priority_rows, widths=[85 * mm, 45 * mm]))

        visible = [c for c in [
            "Date", "Display_Priority", "Overall_Anomaly_Severity",
            "Affected_KPI_Count", "Owner", "Supporting_Owner",
            "Recommended_Action"
        ] if c in alert_data.columns]
        if visible:
            alert_rows = [[
                "Date", "Priority", "Severity", "KPIs", "Owner",
                "Supporting owner", "Recommended action"
            ]]
            for _, row in alert_data.sort_values("Date", ascending=False).head(25).iterrows():
                alert_rows.append([
                    pd.to_datetime(row.get("Date")).strftime("%d %b %Y"),
                    row.get("Display_Priority", ""),
                    row.get("Overall_Anomaly_Severity", ""),
                    row.get("Affected_KPI_Count", ""),
                    row.get("Owner", ""),
                    row.get("Supporting_Owner", ""),
                    row.get("Recommended_Action", ""),
                ])
            story.append(Spacer(1, 2 * mm))
            story.append(make_table(alert_rows))
    else:
        story.append(Paragraph("No alerts match the selected dashboard filters.", styles["NarrativeText"]))

    # Category investigation: contribution and actual category totals.
    story.append(PageBreak())
    story.append(Paragraph("4. Category Investigation", styles["SectionHeading"]))
    category_data = prod.copy()
    if not category_data.empty and "Category" in category_data.columns:
        agg_map = {}
        if "Orders" in category_data.columns:
            agg_map["Orders"] = ("Orders", "sum")
        if "Revenue_INR" in category_data.columns:
            agg_map["Revenue"] = ("Revenue_INR", "sum")
        if agg_map:
            cat_table_df = category_data.groupby("Category", as_index=False).agg(**agg_map)
            if "Orders" in cat_table_df.columns:
                total = pd.to_numeric(cat_table_df["Orders"], errors="coerce").sum()
                cat_table_df["Orders share (%)"] = (
                    pd.to_numeric(cat_table_df["Orders"], errors="coerce") / total * 100
                    if total else 0
                )
            if "Revenue" in cat_table_df.columns:
                total_rev = pd.to_numeric(cat_table_df["Revenue"], errors="coerce").sum()
                cat_table_df["Revenue share (%)"] = (
                    pd.to_numeric(cat_table_df["Revenue"], errors="coerce") / total_rev * 100
                    if total_rev else 0
                )
            cat_table_df = cat_table_df.sort_values(
                "Revenue" if "Revenue" in cat_table_df.columns else "Orders",
                ascending=False
            )
            cat_rows = [["Category"] + [c for c in cat_table_df.columns if c != "Category"]]
            for _, row in cat_table_df.iterrows():
                vals = [row["Category"]]
                for col in cat_table_df.columns:
                    if col == "Category":
                        continue
                    if "share" in col.lower():
                        vals.append(f"{row[col]:.1f}%")
                    elif col == "Revenue":
                        vals.append(f"₹{row[col]:,.2f}")
                    else:
                        vals.append(f"{row[col]:,.0f}")
                cat_rows.append(vals)
            story.append(make_table(cat_rows))
            # Reuse the dashboard's category actual-vs-expected investigation
            # when that view has been calculated for the current selection.
            current_category_results = globals().get("results")
            if isinstance(current_category_results, pd.DataFrame) and not current_category_results.empty:
                comparison_rows = [["Category", "Actual", "Expected", "Unfavourable gap", "Status"]]
                for _, crow in current_category_results.iterrows():
                    comparison_rows.append([
                        str(crow.get("Category", "")),
                        f"{crow.get('Actual', float('nan')):,.2f}" if pd.notna(crow.get("Actual")) else "N/A",
                        f"{crow.get('Expected', float('nan')):,.2f}" if pd.notna(crow.get("Expected")) else "N/A",
                        f"{crow.get('Gap', float('nan')):,.2f}" if pd.notna(crow.get("Gap")) else "N/A",
                        str(crow.get("Status", "")),
                    ])
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(
                    "Actual vs expected by category (dashboard calculation)",
                    styles["NarrativeText"]
                ))
                story.append(make_table(comparison_rows))
            # Revenue by category chart
            if "Revenue" in cat_table_df.columns:
                fig, ax = plt.subplots(figsize=(7.0, 2.8))
                plot_df = cat_table_df.sort_values("Revenue", ascending=True)
                ax.barh(plot_df["Category"].astype(str), plot_df["Revenue"])
                ax.set_title("Revenue by category", fontsize=10)
                ax.set_xlabel("Revenue (INR)")
                ax.grid(axis="x", alpha=0.25)
                fig.tight_layout()
                chart_buffer = io.BytesIO()
                fig.savefig(chart_buffer, format="png", dpi=130, bbox_inches="tight")
                plt.close(fig)
                chart_buffer.seek(0)
                story.append(Spacer(1, 2 * mm))
                story.append(RLImage(chart_buffer, width=165 * mm, height=65 * mm))
        else:
            story.append(Paragraph("Category KPI fields are unavailable in product_data.csv.", styles["NarrativeText"]))
    else:
        story.append(Paragraph("No category-level records match the selected filters.", styles["NarrativeText"]))

    # Product investigation: product contribution and simple adverse-signal evidence.
    story.append(Paragraph("5. Product-Level Investigation", styles["SectionHeading"]))
    if not prod.empty and "Product_Name" in prod.columns:
        product_agg = {}
        if "Orders" in prod.columns:
            product_agg["Orders"] = ("Orders", "sum")
        if "Revenue_INR" in prod.columns:
            product_agg["Revenue"] = ("Revenue_INR", "sum")
        if product_agg:
            product_table_df = prod.groupby(
                ["Category", "Product_Name"], as_index=False
            ).agg(**product_agg)
            sort_col = "Revenue" if "Revenue" in product_table_df.columns else "Orders"
            product_table_df = product_table_df.sort_values(sort_col, ascending=False).head(15)
            prod_rows = [["Category", "Product"] + list(product_agg.keys())]
            for _, row in product_table_df.iterrows():
                prod_rows.append([
                    str(row["Category"]), str(row["Product_Name"]),
                    *[
                        (f"₹{row[c]:,.2f}" if c == "Revenue" else f"{row[c]:,.0f}")
                        for c in product_agg.keys()
                    ]
                ])
            story.append(Paragraph(
                "Top 15 products by revenue (or orders where revenue is unavailable), "
                "within the selected date, geography and category filters.",
                styles["NarrativeText"]
            ))
            story.append(make_table(prod_rows))
        else:
            story.append(Paragraph("Product KPI fields are unavailable.", styles["NarrativeText"]))

        # Include the actual product anomaly evidence calculated by the dashboard
        # when Product Anomaly Investigation is the selected view.
        if globals().get("product_view") == "Product Anomaly Investigation":
            current_anomalies = globals().get("anomaly_rows")
            if isinstance(current_anomalies, pd.DataFrame) and not current_anomalies.empty:
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(
                    "Products with potential adverse anomalies (same selected KPI and filters)",
                    styles["NarrativeText"]
                ))
                anomaly_cols = [
                    c for c in [
                        "Date", "Category", "Product_Name", metric_col,
                        "Expected", "Deviation_Pct", "MAD"
                    ] if c in current_anomalies.columns
                ]
                anomaly_rows_pdf = [[
                    "Anomaly date" if c == "Date" else
                    "Product" if c == "Product_Name" else
                    "Actual" if c == metric_col else
                    "Expected baseline" if c == "Expected" else
                    "Adverse deviation (%)" if c == "Deviation_Pct" else
                    "Historical MAD" if c == "MAD" else c
                    for c in anomaly_cols
                ]]
                for _, arow in current_anomalies[anomaly_cols].head(30).iterrows():
                    vals = []
                    for c in anomaly_cols:
                        value = arow[c]
                        if c == "Date":
                            value = pd.to_datetime(value).strftime("%d %b %Y")
                        elif isinstance(value, (int, float)) and pd.notna(value):
                            value = f"{value:,.2f}"
                        vals.append(value)
                    anomaly_rows_pdf.append(vals)
                story.append(make_table(anomaly_rows_pdf))
            else:
                story.append(Paragraph(
                    "No product-level adverse anomalies were detected for the selected KPI, "
                    "category, geography and date range, or no anomaly evidence table was available.",
                    styles["NarrativeText"]
                ))
    else:
        story.append(Paragraph("No product-level records match the selected filters.", styles["NarrativeText"]))

    # Selected alert narrative and Google Search sources, if generated.
    story.append(PageBreak())
    story.append(Paragraph("6. Investigation Narrative", styles["SectionHeading"]))
    narrative_date = st.session_state.get("gemini_narrative_date")
    narrative_text = st.session_state.get("gemini_narrative_text")
    narrative_citations = st.session_state.get("gemini_narrative_citations", [])

    if narrative_text and narrative_date and str(narrative_date) == str(
        globals().get("selected_date", "")
    ):
        story.append(Paragraph(
            f"<b>Gemini narrative for alert date:</b> {escape(str(narrative_date))}",
            styles["NarrativeText"]
        ))
        for paragraph_text in str(narrative_text).split("\n"):
            clean = escape(paragraph_text.strip())
            if clean:
                story.append(Paragraph(clean, styles["NarrativeText"]))
        if narrative_citations:
            story.append(Paragraph("External research sources", styles["SectionHeading"]))
            for source in narrative_citations:
                title = escape(str(source.get("title", "Source")))
                url = escape(str(source.get("url", "")))
                if url:
                    story.append(Paragraph(
                        f'<link href="{url}" color="#1769AA">{title}</link>',
                        styles["SmallText"]
                    ))
    elif "selected_row" in globals() or "selected_row" in locals():
        story.append(Paragraph(
            "A Gemini narrative has not been generated for the selected alert. "
            "The rule-based investigation summary is included below where available.",
            styles["NarrativeText"]
        ))
        try:
            rule_row = selected_row
            affected_text, hypothesis_text, confidence_text, evidence_items = build_narrative(rule_row)
            story.append(Paragraph(f"<b>Affected KPIs:</b> {escape(str(affected_text))}", styles["NarrativeText"]))
            story.append(Paragraph(f"<b>Hypothesis:</b> {escape(str(hypothesis_text))}", styles["NarrativeText"]))
            story.append(Paragraph(f"<b>Confidence:</b> {escape(str(confidence_text))}", styles["NarrativeText"]))
            for item in evidence_items:
                story.append(Paragraph("• " + escape(str(item)), styles["NarrativeText"]))
        except Exception:
            story.append(Paragraph(
                "No selected-alert narrative is available. Refer to the alert table for findings and ownership.",
                styles["NarrativeText"]
            ))
    else:
        story.append(Paragraph(
            "No Gemini narrative has been generated. The report includes dashboard metrics and alert evidence.",
            styles["NarrativeText"]
        ))

    story.append(Paragraph("7. Ownership & Recommended Actions", styles["SectionHeading"]))
    if not alert_data.empty:
        ownership_rows = [["Alert date", "Priority", "Owner", "Supporting owner", "Recommended action"]]
        for _, row in alert_data.sort_values("Date", ascending=False).head(20).iterrows():
            ownership_rows.append([
                pd.to_datetime(row.get("Date")).strftime("%d %b %Y"),
                row.get("Display_Priority", ""),
                row.get("Owner", "Not assigned"),
                row.get("Supporting_Owner", "Not assigned"),
                row.get("Recommended_Action", "Validate anomaly evidence"),
            ])
        story.append(make_table(ownership_rows))
    else:
        story.append(Paragraph("No alert ownership records match the selected filters.", styles["NarrativeText"]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("8. Interpretation & Limitations", styles["SectionHeading"]))
    story.append(Paragraph(
        "Anomaly flags and root-cause hypotheses are investigation signals, not proof of causation. "
        "Category and product summaries are calculated from the available product-level dataset. "
        "External event context is included only when a Gemini narrative and source citations have "
        "already been generated. Validate findings against operational records before taking action.",
        styles["NarrativeText"]
    ))

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(15 * mm, 9 * mm, "E-Commerce Anomaly Intelligence | Confidential project report")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer.getvalue()


pdf_col1, pdf_col2 = st.columns([1, 3])
with pdf_col1:
    generate_pdf_clicked = st.button(
        "Generate Investigation PDF",
        type="primary",
        key="generate_investigation_pdf"
    )

if generate_pdf_clicked:
    try:
        with st.spinner("Preparing your PDF investigation report..."):
            pdf_bytes = build_investigation_pdf()
        st.session_state["investigation_pdf_bytes"] = pdf_bytes
        st.session_state["investigation_pdf_name"] = (
            f"Ecommerce_Investigation_Report_{start_date}_{end_date}.pdf"
        )
        st.success("Your investigation report is ready.")
    except ImportError as exc:
        st.error(
            "PDF report dependencies are missing. Add 'reportlab' and 'matplotlib' "
            "to requirements.txt in your GitHub repository, then wait for Streamlit "
            f"to redeploy. Details: {exc}"
        )
    except Exception as exc:
        st.error(f"Could not generate the PDF report: {type(exc).__name__}: {str(exc)[:500]}")

if st.session_state.get("investigation_pdf_bytes"):
    st.download_button(
        "Download PDF Report",
        data=st.session_state["investigation_pdf_bytes"],
        file_name=st.session_state.get(
            "investigation_pdf_name", "Ecommerce_Investigation_Report.pdf"
        ),
        mime="application/pdf",
        key="download_investigation_pdf"
    )


# ==================================================
# 13. FOOTER
# ==================================================
st.divider()
st.caption(
    "E-Commerce Anomaly Intelligence | Historical data | "
    "Statistical anomaly signals + evidence-led investigation + ownership"
)
