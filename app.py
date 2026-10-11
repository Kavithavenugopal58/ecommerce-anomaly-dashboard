
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

st.markdown(
    """
    <style>
    .block-container {
        max-width: 100%;
        padding-left: 2rem;
        padding-right: 2rem;
        padding-top: 1.5rem;
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
    <div style="
        background: linear-gradient(110deg, #10284A, #245B86);
        padding: 24px;
        border-radius: 12px;
        color: white;">
        <h1 style="margin:0;">E-Commerce Anomaly Intelligence</h1>
        <p style="margin:8px 0 0 0;">
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
        background: linear-gradient(135deg, #10284A, #245B86);
        border-radius: 14px;
        padding: 20px 18px;
        min-height: 125px;
        color: white;
        box-shadow: 0 4px 12px rgba(16, 40, 74, 0.15);
        border-bottom: 4px solid #58B4E8;
    }
    .kpi-label {
        font-size: 14px;
        font-weight: 500;
        color: #DCEBFA;
        margin-bottom: 12px;
    }
    .kpi-value {
        font-size: 27px;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.25;
        overflow-wrap: anywhere;
    }
    .kpi-note {
        font-size: 11px;
        color: #DCEBFA;
        margin-top: 9px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Four cards in one row
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">TOTAL ORDERS</div>
            <div class="kpi-value">{orders_text}</div>
            <div class="kpi-note">Sum across selected dates</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">TOTAL REVENUE</div>
            <div class="kpi-value">{revenue_text}</div>
            <div class="kpi-note">Sum across selected dates</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">WEIGHTED AOV</div>
            <div class="kpi-value">{aov_text}</div>
            <div class="kpi-note">Revenue ÷ orders</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with kpi4:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">AVG. CANCELLATION RATE</div>
            <div class="kpi-value">{cancellation_text}</div>
            <div class="kpi-note">Average of daily rates</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==================================================
# 8. FOUR KPI TRENDS — SHOWN TOGETHER
# ==================================================
st.subheader("KPI Trend Overview")
st.caption(
    "All four KPIs are shown for the selected date range. "
    "The dashed line is the expected baseline; red markers identify "
    "dates flagged as anomalies by the existing detector."
)

def add_kpi_chart(column, title, actual_col, expected_col, flag_col):
    fig = go.Figure()

    if actual_col not in det.columns:
        column.warning(f"Missing column: {actual_col}")
        return

    chart_data = det.sort_values("Date").copy()

    fig.add_trace(go.Scatter(
        x=chart_data["Date"],
        y=chart_data[actual_col],
        mode="lines+markers",
        name="Actual",
        line=dict(width=2.5, color="#2675C9"),
        hovertemplate="%{x|%d %b %Y}<br>Actual: %{y:,.2f}<extra></extra>"
    ))

    if expected_col in chart_data.columns:
        fig.add_trace(go.Scatter(
            x=chart_data["Date"],
            y=chart_data[expected_col],
            mode="lines",
            name="Expected",
            line=dict(dash="dash", width=2, color="#E0A23D"),
            hovertemplate="%{x|%d %b %Y}<br>Expected: %{y:,.2f}<extra></extra>"
        ))

    if flag_col in chart_data.columns:
        anomaly_mask = chart_data[flag_col].apply(is_true)
        anomalies = chart_data[anomaly_mask].dropna(
            subset=[actual_col]
        )

        if not anomalies.empty:
            fig.add_trace(go.Scatter(
                x=anomalies["Date"],
                y=anomalies[actual_col],
                mode="markers",
                name="Anomaly",
                marker=dict(
                    color="#D64545",
                    size=9,
                    symbol="circle"
                ),
                hovertemplate=(
                    "%{x|%d %b %Y}<br>"
                    "Anomaly value: %{y:,.2f}<extra></extra>"
                )
            ))

    fig.update_layout(
        title=title,
        height=330,
        margin=dict(l=10, r=10, t=45, b=10),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0
        ),
        xaxis_title=None,
        yaxis_title=None
    )

    column.plotly_chart(fig, use_container_width=True)

# Two rows, two charts per row
orders_col, revenue_col = st.columns(2)

add_kpi_chart(
    orders_col,
    "Orders",
    "Total_Orders",
    "Total_Orders_Expected",
    "Orders_Is_Anomaly"
)

add_kpi_chart(
    revenue_col,
    "Revenue (INR)",
    "Total_Revenue_INR",
    "Total_Revenue_INR_Expected",
    "Revenue_Is_Anomaly"
)

aov_col, cancellation_col = st.columns(2)

add_kpi_chart(
    aov_col,
    "Average Order Value (INR)",
    "Weighted_AOV_INR",
    "Weighted_AOV_INR_Expected",
    "AOV_Is_Anomaly"
)

add_kpi_chart(
    cancellation_col,
    "Cancellation Rate (%)",
    "Avg_Cancellation_Rate_Pct",
    "Avg_Cancellation_Rate_Pct_Expected",
    "Cancellation_Rate_Is_Anomaly"
)




# ==================================================
# 9. ALERT PRIORITY AND INTERACTIVE CATEGORY INVESTIGATION
# ==================================================

left, right = st.columns(2)

# --------------------------------------------------
# LEFT: ALERT PRIORITY PIE CHART
# --------------------------------------------------
with left:
    st.subheader("Alerts by Priority")

    if not alert_data.empty:
        priority_counts = (
            alert_data["Display_Priority"]
            .value_counts()
            .rename_axis("Priority")
            .reset_index(name="Alerts")
        )

        priority_fig = px.pie(
            priority_counts,
            names="Priority",
            values="Alerts",
            hole=0.5
        )

        priority_fig.update_layout(height=350)

        st.plotly_chart(
            priority_fig,
            use_container_width=True
        )
    else:
        st.info(
            "No alerts match the selected date and priority filters."
        )


# --------------------------------------------------
# RIGHT: CATEGORY INVESTIGATION
# Uses the entire selected date range
# --------------------------------------------------
with right:
    st.subheader("Category Investigation")

    category_metric = st.selectbox(
        "Analyse categories by",
        [
            "Orders",
            "Revenue (INR)",
            "Weighted AOV (INR)",
            "Cancellation Rate (%)"
        ],
        key="category_investigation_metric"
    )

    # 'prod' already contains the selected date range
    # and the applied Geography/Category filters.
    if not prod.empty and "Category" in prod.columns:

        # Aggregate orders and revenue across the selected period
        category_data = (
            prod.groupby("Category", as_index=False)
            .agg(
                Orders=("Orders", "sum"),
                Revenue_INR=("Revenue_INR", "sum")
            )
        )

        # Weighted AOV = total revenue / total orders
        category_data["Weighted AOV (INR)"] = (
            category_data["Revenue_INR"]
            / category_data["Orders"].replace(0, float("nan"))
        )

        # Calculate order-weighted cancellation rate
        cancellation_data = prod.copy()

        cancellation_data["Weighted_Cancellation"] = (
            cancellation_data["Cancellation_Rate_Pct"]
            * cancellation_data["Orders"]
        )

        cancellation_numerator = (
            cancellation_data.groupby("Category")[
                "Weighted_Cancellation"
            ].sum()
        )

        cancellation_orders = (
            cancellation_data.groupby("Category")["Orders"].sum()
        )

        category_data["Cancellation Rate (%)"] = (
            category_data["Category"].map(cancellation_numerator)
            / category_data["Category"].map(
                cancellation_orders
            ).replace(0, float("nan"))
        )

        # Map the selected metric to its column
        metric_columns = {
            "Orders": "Orders",
            "Revenue (INR)": "Revenue_INR",
            "Weighted AOV (INR)": "Weighted AOV (INR)",
            "Cancellation Rate (%)": "Cancellation Rate (%)"
        }

        value_column = metric_columns[category_metric]

        chart_data = (
            category_data[["Category", value_column]]
            .dropna()
            .sort_values(value_column, ascending=False)
        )

        if not chart_data.empty:
            category_fig = px.bar(
                chart_data,
                x="Category",
                y=value_column,
                title=f"{category_metric} by Category",
                text_auto=".2s"
            )

            category_fig.update_layout(
                height=350,
                xaxis_title="Category",
                yaxis_title=category_metric,
                xaxis_tickangle=-25,
                margin=dict(l=10, r=10, t=50, b=10),
                showlegend=False
            )

            category_fig.update_traces(
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + category_metric
                    + ": %{y:,.2f}<extra></extra>"
                )
            )

            st.plotly_chart(
                category_fig,
                use_container_width=True
            )

            st.caption(
                f"Date range: {start_date} to {end_date}. "
                f"Geography: {geo}; Category filter: {category}."
            )

            # Validation totals for Orders and Revenue
            if category_metric == "Orders":
                category_total = category_data["Orders"].sum()
                product_total = prod["Orders"].sum()

                st.caption(
                    f"Category total: {category_total:,.0f} orders | "
                    f"Filtered product-data total: {product_total:,.0f}"
                )

            elif category_metric == "Revenue (INR)":
                category_total = category_data["Revenue_INR"].sum()
                product_total = prod["Revenue_INR"].sum()

                st.caption(
                    f"Category total: ₹{category_total:,.2f} | "
                    f"Filtered product-data total: ₹{product_total:,.2f}"
                )

        else:
            st.info(
                "No values are available for this metric and filter selection."
            )

    else:
        st.info(
            "No product data matches the selected date range and filters."
        )

# ==================================================
# 10. PRODUCT-LEVEL INVESTIGATION — PIE CHART
# ==================================================
st.subheader("Product-Level Investigation")

if not prod.empty and "Product_Name" in prod.columns:
    product_breakdown = (
        prod.groupby("Product_Name", as_index=False)
        .agg(
            Orders=("Orders", "sum"),
            Revenue_INR=("Revenue_INR", "sum"),
            Cancellation_Rate_Pct=("Cancellation_Rate_Pct", "mean")
        )
        .sort_values("Orders", ascending=False)
    )

    # Choose what the pie chart should show
    chart_metric = st.selectbox(
        "Product breakdown by",
        ["Orders", "Revenue (INR)", "Cancellation Rate (%)"]
    )

    metric_columns = {
        "Orders": "Orders",
        "Revenue (INR)": "Revenue_INR",
        "Cancellation Rate (%)": "Cancellation_Rate_Pct"
    }

    value_column = metric_columns[chart_metric]

    pie_data = product_breakdown[
        product_breakdown[value_column].notna()
        & (product_breakdown[value_column] >= 0)
    ].copy()

    if not pie_data.empty and pie_data[value_column].sum() > 0:
        fig_product = px.pie(
            pie_data,
            names="Product_Name",
            values=value_column,
            title=f"{chart_metric} by Product",
            hole=0.30
        )

        fig_product.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Value: %{value:,.2f}<br>"
                "Share: %{percent}<extra></extra>"
            )
        )

        fig_product.update_layout(
            height=480,
            legend_title_text="Product",
            margin=dict(l=10, r=10, t=60, b=10)
        )

        st.plotly_chart(
            fig_product,
            use_container_width=True
        )

        st.caption(
            "The pie chart shows each product's share of the selected "
            "metric. It describes contribution, not the cause of an anomaly."
        )
    else:
        st.info("No positive values are available for this chart metric.")
else:
    st.info("No product data matches the selected filters.")



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
            background-color: #eef2f7;
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
# 12. ALERT INVESTIGATION AND RULE-BASED NARRATIVE
# ==================================================
st.subheader("Alert Investigation & Narrative")

if not alert_data.empty:
    choices = alert_data.sort_values("Date", ascending=False).copy()
    choices["Date_Label"] = choices["Date"].dt.strftime("%Y-%m-%d")

    selected_date = st.selectbox(
        "Select an alert date",
        choices["Date_Label"].tolist()
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
    st.write("**Root-cause hypothesis:**", hypothesis)
    st.write("**Confidence:**", confidence)

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
    st.write("**Recommended action:**", recommended_action)

    st.info(
        "This is a rule-based investigation narrative. The root cause "
        "is a hypothesis, not a confirmed finding."
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
