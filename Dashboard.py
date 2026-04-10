from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent / "Data" / "Processed"
BAR_COLOR = "#E36414"
SECONDARY_COLOR = "#457B9D"


@st.cache_data(show_spinner=False)
def load_main_data() -> pd.DataFrame:
    path = DATA_DIR / "all_data_dashboard.csv"
    df = pd.read_csv(path, low_memory=False)

    df["order_purchase_timestamp"] = pd.to_datetime(df.get("order_purchase_timestamp"), errors="coerce") # type: ignore
    df["order_delivered_customer_date"] = pd.to_datetime(df.get("order_delivered_customer_date"), errors="coerce") # type: ignore
    df["order_estimated_delivery_date"] = pd.to_datetime(df.get("order_estimated_delivery_date"), errors="coerce") # type: ignore

    numeric_cols = [
        "price",
        "freight_value",
        "qty",
        "total_price",
        "review_score_x",
        "review_score_y",
        "on_time",
        "diff_days",
        "shipping_duration",
        "estimated_duration",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "review_score" not in df.columns:
        if "review_score_x" in df.columns and "review_score_y" in df.columns:
            df["review_score"] = df["review_score_x"].fillna(df["review_score_y"])
        elif "review_score_x" in df.columns:
            df["review_score"] = df["review_score_x"]
        elif "review_score_y" in df.columns:
            df["review_score"] = df["review_score_y"]

    if "total_price" not in df.columns and {"price", "qty"}.issubset(df.columns):
        df["total_price"] = df["price"] * df["qty"]

    df["purchase_date"] = df["order_purchase_timestamp"].dt.date
    df["purchase_month"] = (
        df["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    )

    return df


@st.cache_data(show_spinner=False)
def load_sales_by_category() -> pd.DataFrame:
    path = DATA_DIR / "sales_by_category.csv"
    df = pd.read_csv(path)
    for col in ["price", "qty", "freight_value", "review_score_y"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_sales_by_state() -> pd.DataFrame:
    path = DATA_DIR / "sales_by_state.csv"
    df = pd.read_csv(path)
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_rfm_segments() -> pd.DataFrame:
    path = DATA_DIR / "rfm_segments.csv"
    df = pd.read_csv(path)
    return df


def filter_main_data(df: pd.DataFrame) -> pd.DataFrame:
    df_filtered = df.copy()

    min_date = df_filtered["purchase_date"].min()
    max_date = df_filtered["purchase_date"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        return df_filtered

    with st.expander("🔍 Filters", expanded=True):
        date_range = st.date_input("Purchase date range", (min_date, max_date))

        status_options = sorted(
            [status for status in df_filtered["order_status"].dropna().unique()]
        )
        status_selected = st.multiselect(
            "Order status",
            status_options,
        )

        state_options = sorted(
            [state for state in df_filtered["customer_state"].dropna().unique()]
        )
        state_selected = st.multiselect(
            "Customer state",
            state_options,
        )

        segment_options = sorted(
            [segment for segment in df_filtered["customer_segment"].dropna().unique()]
        )
        segment_selected = st.multiselect(
            "Customer segment",
            segment_options,
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[
            (df_filtered["purchase_date"] >= start_date)
            & (df_filtered["purchase_date"] <= end_date)
        ]

    if status_selected:
        df_filtered = df_filtered[df_filtered["order_status"].isin(status_selected)]

    if state_selected:
        df_filtered = df_filtered[df_filtered["customer_state"].isin(state_selected)]

    if segment_selected:
        df_filtered = df_filtered[
            df_filtered["customer_segment"].isin(segment_selected)
        ]

    return df_filtered


def style_plotly_figure(
    fig,
    title: str,
    x_title: str,
    y_title: str,
) -> None:
    fig.update_layout(
        title=f"<b>{title}</b>",
        template="plotly_white",
        xaxis_title=x_title,
        yaxis_title=y_title,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=60, l=20, r=20, b=20),
    )


def plot_time_series(df: pd.DataFrame) -> None:
    monthly = (
        df.dropna(subset=["purchase_month"])
        .groupby("purchase_month")["order_id"]
        .nunique()
        .reset_index(name="orders")
    )
    if monthly.empty:
        st.info("No orders available for the selected period.")
        return

    fig = px.line(
        monthly,
        x="purchase_month",
        y="orders",
        markers=True,
        color_discrete_sequence=[BAR_COLOR],
    )
    fig.update_traces(line=dict(width=3))
    style_plotly_figure(fig, "Orders Over Time", "Month", "Orders")
    st.plotly_chart(fig, use_container_width=True)


def plot_top_categories(df: pd.DataFrame) -> None:
    category_col = (
        "product_category_name_english"
        if "product_category_name_english" in df.columns
        else "product_category_name"
    )
    category_sales = (
        df.dropna(subset=[category_col])
        .groupby(category_col)["total_price"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index(name="revenue")
    )
    if category_sales.empty:
        st.info("No category revenue data available for the selected filters.")
        return

    fig = px.bar(
        category_sales.sort_values("revenue"),
        x="revenue",
        y=category_col,
        orientation="h",
        color_discrete_sequence=[BAR_COLOR] * len(category_sales),
    )
    style_plotly_figure(fig, "Top 10 Categories by Revenue", "Revenue", "Category")
    st.plotly_chart(fig, use_container_width=True)


def plot_state_sales(df: pd.DataFrame) -> None:
    state_sales = (
        df.dropna(subset=["customer_state"])
        .groupby("customer_state")["total_price"]
        .sum()
        .sort_values(ascending=False)
        .reset_index(name="revenue")
    )
    if state_sales.empty:
        st.info("No state-level sales data available for the selected filters.")
        return

    fig = px.bar(
        state_sales,
        x="customer_state",
        y="revenue",
        color_discrete_sequence=[SECONDARY_COLOR] * len(state_sales),
    )
    fig.update_xaxes(categoryorder="total descending")
    style_plotly_figure(fig, "Revenue by Customer State", "State", "Revenue")
    st.plotly_chart(fig, use_container_width=True)


def plot_review_distribution(df: pd.DataFrame) -> None:
    if "review_score" not in df.columns:
        st.info("Review score data not available for the current filter selection.")
        return

    review_counts = (
        df.dropna(subset=["review_score"])
        .groupby("review_score")["order_id"]
        .nunique()
        .reset_index(name="orders")
    )
    if review_counts.empty:
        st.info("No review score data available for the selected filters.")
        return

    fig = px.bar(
        review_counts,
        x="review_score",
        y="orders",
        color_discrete_sequence=[BAR_COLOR],
    )
    fig.update_xaxes(dtick=1)
    style_plotly_figure(fig, "Review Score Distribution", "Review Score", "Orders")
    st.plotly_chart(fig, use_container_width=True)


def plot_delivery_performance(df: pd.DataFrame) -> None:
    if "diff_days" not in df.columns:
        st.info("Delivery timing data is not available for the current filter selection.")
        return

    diff_days = df["diff_days"].dropna()
    if diff_days.empty:
        st.info("No delivery timing data available for the selected filters.")
        return

    fig = px.histogram(
        diff_days,
        nbins=30,
        color_discrete_sequence=[SECONDARY_COLOR],
    )
    style_plotly_figure(
        fig,
        "Delivery Timing (Days vs Estimate)",
        "Days (positive = late, negative = early)",
        "Orders",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_rfm_segments(df: pd.DataFrame) -> None:
    if "customer_segment" not in df.columns:
        st.info("Customer segment data not available.")
        return

    segment_counts = (
        df.dropna(subset=["customer_segment"])
        .groupby("customer_segment")["customer_unique_id"]
        .nunique()
        .sort_values(ascending=False)
        .reset_index(name="customers")
    )
    if segment_counts.empty:
        st.info("No customer segment data available for the selected filters.")
        return

    fig = px.bar(
        segment_counts.sort_values("customers"),
        y="customer_segment",
        x="customers",
        orientation="h",
        color_discrete_sequence=[BAR_COLOR] * len(segment_counts),
    )
    style_plotly_figure(fig, "Customer Segments (RFM)", "Customers", "Segment")
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Brazilian E-commerce Dashboard",
        layout="wide",
    )

    # Page Navigation
    page = st.selectbox(
        "📍 Navigation",
        ["Home", "Analysis & Filters"],
        index=0,
    )

    if page == "Home":
        show_home_page()
    else:
        show_analysis_page()


def show_home_page() -> None:
    st.title("Brazilian E-commerce Analysis Dashboard")
    st.caption("Overview of the Brazilian E-commerce dataset - All Data")

    try:
        with st.spinner("Loading data..."):
            main_df = load_main_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    try:
        # Show metrics for all data (no filters)
        total_orders = main_df["order_id"].nunique()
        total_revenue = main_df["total_price"].sum()
        unique_customers = main_df["customer_unique_id"].nunique()
        avg_order_value = total_revenue / total_orders if total_orders else 0
        avg_freight = main_df["freight_value"].mean()
        on_time_rate = main_df["on_time"].mean() if "on_time" in main_df.columns else np.nan
        avg_review = main_df["review_score"].mean() if "review_score" in main_df.columns else np.nan

        st.subheader("📊 Key Metrics (All Data)")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Total Orders", f"{total_orders:,.0f}")
        kpi_cols[1].metric("Total Revenue", f"${total_revenue:,.2f}")
        kpi_cols[2].metric("Unique Customers", f"{unique_customers:,.0f}")
        kpi_cols[3].metric("Avg Order Value", f"${avg_order_value:,.2f}")

        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Avg Freight Cost", f"${avg_freight:,.2f}")
        kpi_cols[1].metric("On-time Delivery Rate", "N/A" if np.isnan(on_time_rate) else f"{on_time_rate:.1%}")
        kpi_cols[2].metric("Avg Review Score", "N/A" if np.isnan(avg_review) else f"{avg_review:.2f}")

        st.divider()

        st.subheader("📈 Key Visualizations")
        
        with st.expander("Orders Over Time", expanded=True):
            plot_time_series(main_df)

        with st.expander("Review Score Distribution"):
            plot_review_distribution(main_df)

        with st.expander("Top 10 Categories by Revenue"):
            plot_top_categories(main_df)

        with st.expander("Revenue by Customer State"):
            plot_state_sales(main_df)

        with st.expander("Delivery Performance"):
            plot_delivery_performance(main_df)

        with st.expander("Customer Segments (RFM Analysis)"):
            plot_rfm_segments(main_df)

        st.divider()
        st.info("💡 Go to **Analysis & Filters** page to explore the data with custom filters!")

    except Exception as e:
        st.error(f"Error displaying dashboard: {str(e)}")
        import traceback
        st.write("Debug info:")
        st.write(traceback.format_exc())


def show_analysis_page() -> None:
    st.title("Brazilian E-commerce Analysis & Filters")
    st.caption("Explore the data with custom filters")

    try:
        with st.spinner("Loading data..."):
            main_df = load_main_data()
            sales_by_category = load_sales_by_category()
            sales_by_state = load_sales_by_state()
            rfm_segments = load_rfm_segments()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    try:
        filtered_df = filter_main_data(main_df)
    except Exception as e:
        st.error(f"Error filtering data: {e}")
        return

    try:
        total_orders = filtered_df["order_id"].nunique()
        total_revenue = filtered_df["total_price"].sum()
        unique_customers = filtered_df["customer_unique_id"].nunique()
        avg_order_value = total_revenue / total_orders if total_orders else 0
        avg_freight = filtered_df["freight_value"].mean()
        on_time_rate = filtered_df["on_time"].mean() if "on_time" in filtered_df.columns else np.nan
        avg_review = filtered_df["review_score"].mean() if "review_score" in filtered_df.columns else np.nan

        st.subheader("📊 Filtered Data Summary")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Orders", f"{total_orders:,.0f}")
        kpi_cols[1].metric("Revenue", f"${total_revenue:,.2f}")
        kpi_cols[2].metric("Customers", f"{unique_customers:,.0f}")
        kpi_cols[3].metric("Avg Order Value", f"${avg_order_value:,.2f}")

        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Avg Freight", f"${avg_freight:,.2f}")
        kpi_cols[1].metric(
            "On-time Delivery", "N/A" if np.isnan(on_time_rate) else f"{on_time_rate:.1%}"
        )
        kpi_cols[2].metric(
            "Avg Review Score", "N/A" if np.isnan(avg_review) else f"{avg_review:.2f}"
        )

        st.divider()

        with st.expander("📈 Orders Over Time & Review Scores"):
            col_left, col_right = st.columns([2, 1])
            with col_left:
                plot_time_series(filtered_df)
            with col_right:
                plot_review_distribution(filtered_df)

        with st.expander("📊 Top Categories & State Sales"):
            col_left, col_right = st.columns(2)
            with col_left:
                plot_top_categories(filtered_df)
            with col_right:
                plot_state_sales(filtered_df)

        with st.expander("🚚 Delivery Performance & Customer Segments"):
            col_left, col_right = st.columns(2)
            with col_left:
                plot_delivery_performance(filtered_df)
            with col_right:
                plot_rfm_segments(filtered_df)

        st.divider()

        st.subheader("Reference Tables")
        tab1, tab2, tab3 = st.tabs(["Category Summary", "State Summary", "RFM Segments"])
        with tab1:
            st.dataframe(sales_by_category, width='stretch')
        with tab2:
            st.dataframe(sales_by_state, width='stretch')
        with tab3:
            st.dataframe(rfm_segments.head(2000), width='stretch')
            st.caption("Showing first 2000 rows for performance.")
    except Exception as e:
        st.error(f"Error displaying dashboard: {str(e)}")
        import traceback
        st.write("Debug info:")
        st.write(traceback.format_exc())


if __name__ == "__main__":
    main()