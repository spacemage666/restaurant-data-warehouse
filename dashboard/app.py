"""Streamlit dashboard for the restaurant data warehouse.

Run from the project root:
    streamlit run dashboard/app.py
"""
import pandas as pd
import streamlit as st

import dashboard_lib as lib

st.set_page_config(page_title="Restaurant Data Warehouse", layout="wide")


@st.cache_data
def get_marts():
    return lib.load_marts()


marts = get_marts()
outlets = lib.outlet_table(marts)
all_dates = marts["mart_daily_sales"]["date_day"]

st.title("Restaurant Data Warehouse Dashboard")
st.caption("Synthetic data for a multi-outlet Japanese curry restaurant: sales, production and food waste.")

# ------------------------------------------------------------ sidebar filters
st.sidebar.header("Filters")

date_range = st.sidebar.date_input(
    "Date range",
    value=(all_dates.min().date(), all_dates.max().date()),
    min_value=all_dates.min().date(),
    max_value=all_dates.max().date(),
)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    start, end = all_dates.min(), all_dates.max()

location_types = sorted(outlets["location_type"].unique())
chosen_types = st.sidebar.multiselect("Location type", location_types, default=location_types)

available = outlets[outlets["location_type"].isin(chosen_types)]
outlet_names = list(available["outlet_name"])
chosen_outlets = st.sidebar.multiselect("Outlet", outlet_names, default=outlet_names)

menu_names = sorted(marts["mart_daily_sales"]["menu_name"].unique())
chosen_menus = st.sidebar.multiselect("Menu (sales and production only)", menu_names, default=menu_names)

outlet_ids = available.loc[available["outlet_name"].isin(chosen_outlets), "outlet_id"]
f = lib.apply_filters(marts, start, end, outlet_ids, chosen_menus)

if f["mart_daily_sales"].empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ------------------------------------------------------------ KPI row
k = lib.kpis(f)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", lib.fmt_idr(k["revenue"]))
c2.metric("Gross profit", lib.fmt_idr(k["gross_profit"]), f"{k['gross_margin_pct']:.1f}% margin")
c3.metric("Portions sold", f"{k['portions_sold']:,.0f}")
c4.metric("Waste rate", f"{k['waste_rate_pct']:.1f}%", help="Portions wasted / portions cooked")
c5.metric("Wasted food cost", lib.fmt_idr(k["wasted_food_cost"]))

tab_sales, tab_waste, tab_purchases = st.tabs(["Sales", "Production and food waste", "Purchases"])

# ------------------------------------------------------------ sales tab
with tab_sales:
    st.subheader("Daily revenue by menu item")
    st.line_chart(lib.daily_revenue_by_menu(f["mart_daily_sales"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Top outlets by revenue")
        st.bar_chart(lib.revenue_by_outlet(f["mart_daily_sales"]))
    with right:
        st.subheader("Average portions per outlet by hour")
        st.line_chart(lib.hourly_profile(f["mart_hourly_sales"]))

    st.subheader("Menu margin")
    margin = lib.menu_margin_table(f["mart_daily_sales"]).copy()
    margin["portions"] = margin["portions"].map("{:,.0f}".format)
    margin["revenue"] = margin["revenue"].map("{:,.0f}".format)
    margin["gross_profit"] = margin["gross_profit"].map("{:,.0f}".format)
    margin["gross_margin_pct"] = margin["gross_margin_pct"].map("{:.1f}%".format)
    margin = margin.rename(
        columns={
            "portions": "Portions",
            "revenue": "Revenue (IDR)",
            "gross_profit": "Gross profit (IDR)",
            "gross_margin_pct": "Gross margin",
        }
    )
    margin.index.name = "Menu"
    st.dataframe(margin)

# ------------------------------------------------------------ waste tab
with tab_waste:
    st.subheader("Portions cooked, sold and wasted per day")
    st.line_chart(lib.cooked_vs_sold(f["mart_daily_production"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Waste rate by outlet (%)")
        st.bar_chart(lib.waste_rate_by_outlet(f["mart_daily_production"]))
    with right:
        st.subheader("Top wasted ingredients (IDR)")
        st.bar_chart(lib.top_waste_ingredients(f["mart_waste_by_ingredient"]))

    st.subheader("Waste value per day (IDR)")
    st.line_chart(lib.daily_waste_cost(f["mart_waste_by_ingredient"]))

    st.subheader("Waste by reason")
    reasons = lib.waste_by_reason(f["mart_waste_by_ingredient"]).copy()
    reasons["waste_cost"] = reasons["waste_cost"].map("{:,.0f}".format)
    reasons["share_pct"] = reasons["share_pct"].map("{:.1f}%".format)
    reasons = reasons.rename(columns={"waste_cost": "Waste cost (IDR)", "share_pct": "Share of waste"})
    reasons.index.name = "Reason"
    st.dataframe(reasons)

# ------------------------------------------------------------ purchases tab
with tab_purchases:
    st.metric("Emergency purchases (share of spend)", f"{k['emergency_share_pct']:.1f}%")

    left, right = st.columns(2)
    with left:
        st.subheader("Spend by purchase type (IDR)")
        st.bar_chart(lib.spend_by_type(f["mart_purchases_by_ingredient"]))
    with right:
        st.subheader("Top ingredients by spend (IDR)")
        st.bar_chart(lib.top_purchases(f["mart_purchases_by_ingredient"]))