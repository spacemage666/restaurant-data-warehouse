"""Streamlit dashboard for the restaurant data warehouse.

Run from the project root:
    streamlit run dashboard/app.py
"""
import pandas as pd
import streamlit as st

import charts
import dashboard_lib as lib

st.set_page_config(page_title="Curry Restaurant Dashboard", page_icon="🍛", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    h1 {font-weight: 800; letter-spacing: -0.5px;}
    h3 {margin-top: 0.5rem;}
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #EADFCF; border-radius: 14px;
        padding: 14px 16px; box-shadow: 0 1px 3px rgba(80, 50, 20, 0.06);
    }
    .summary {
        background: #FFF0DC; border-left: 5px solid #D9480F; border-radius: 10px;
        padding: 14px 18px; margin: 8px 0 18px 0; font-size: 1.02rem; line-height: 1.55;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_marts():
    return lib.load_marts()


marts = get_marts()
outlets = lib.outlet_table(marts)
all_dates = marts["mart_daily_sales"]["date_day"]

st.title("🍛 Japanese Curry Restaurant Dashboard")
st.caption("Practice data (synthetic) for a multi-outlet curry restaurant: what we sell, what we cook, and what we throw away.")

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
chosen_types = st.sidebar.multiselect("Type of location", location_types, default=location_types)

available = outlets[outlets["location_type"].isin(chosen_types)]
outlet_names = list(available["outlet_name"])
chosen_outlets = st.sidebar.multiselect("Outlet", outlet_names, default=outlet_names)

menu_names = sorted(marts["mart_daily_sales"]["menu_name"].unique())
chosen_menus = st.sidebar.multiselect("Menu (sales and cooking only)", menu_names, default=menu_names)

outlet_ids = available.loc[available["outlet_name"].isin(chosen_outlets), "outlet_id"]
f = lib.apply_filters(marts, start, end, outlet_ids, chosen_menus)

if f["mart_daily_sales"].empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ------------------------------------------------------------ summary + KPI row
summary = lib.summary_sentences(f)
st.markdown(f'<div class="summary">{" ".join(summary)}</div>', unsafe_allow_html=True)

k = lib.kpis(f)
mom = lib.month_over_month(f["mart_daily_sales"], "revenue")
mom_profit = lib.month_over_month(f["mart_daily_sales"], "gross_profit")
def millions(x):
    """IDR amount as millions, e.g. 9,692 or 666.6"""
    m = x / lib.MILLION
    return f"{m:,.0f}" if abs(m) >= 100 else f"{m:,.1f}"


def vs_last_month(x):
    return None if x is None else f"{x:+.1f}% vs last month"


c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Sales (IDR million)", millions(k["revenue"]), vs_last_month(mom),
          help="Money from customers (all selected outlets).")
c2.metric("Profit* (IDR million)", millions(k["gross_profit"]), vs_last_month(mom_profit),
          help="*Profit before overhead: sales minus the cost of ingredients and packaging. Rent, salaries and electricity are not included.")
c3.metric("Servings sold", f"{k['portions_sold']:,.0f}")
c4.metric("Food thrown away", f"{k['waste_rate_pct']:.1f}%", help="Share of cooked servings that were not sold.")
c5.metric("Waste cost (IDR M)", millions(k["wasted_food_cost"]), help="Ingredient cost of the food thrown away.")

tab_sales, tab_waste, tab_purchases = st.tabs(["💰 Sales", "🗑️ Cooking and food waste", "🛒 Buying ingredients"])

# ------------------------------------------------------------ sales tab
with tab_sales:
    st.subheader("How much do we sell each week?")
    st.altair_chart(charts.line(lib.weekly_revenue_by_menu(f["mart_daily_sales"]), "Week", "Sales (IDR million)", "Menu"))

    left, right = st.columns(2)
    with left:
        st.subheader("Which outlets sell the most?")
        st.altair_chart(charts.hbar(lib.sales_by_outlet(f["mart_daily_sales"]), "Outlet", "Sales (IDR million)"))
    with right:
        st.subheader("When are customers coming?")
        st.altair_chart(charts.line(lib.hourly_long(f["mart_hourly_sales"]), "Hour", "Servings per outlet per day", "Day type", x_type="O", y_title="Avg servings"))

    st.subheader("Which menu earns the most?")
    margin = lib.menu_margin_table(f["mart_daily_sales"]).copy()
    margin["portions"] = margin["portions"].map("{:,.0f}".format)
    margin["revenue"] = margin["revenue"].map("{:,.0f}".format)
    margin["gross_profit"] = margin["gross_profit"].map("{:,.0f}".format)
    margin["gross_margin_pct"] = margin["gross_margin_pct"].map("{:.0f}".format)
    margin = margin.rename(
        columns={
            "portions": "Servings",
            "revenue": "Sales (IDR)",
            "gross_profit": "Profit before overhead (IDR)",
            "gross_margin_pct": "Profit from every IDR 100 sold",
        }
    )
    margin.index.name = "Menu"
    st.dataframe(margin)

# ------------------------------------------------------------ waste tab
with tab_waste:
    st.subheader("Do we cook more than we sell?")
    st.altair_chart(charts.line(lib.weekly_cooked_sold(f["mart_daily_production"]), "Week", "Servings per week", "Servings"))

    left, right = st.columns(2)
    with left:
        st.subheader("Which outlets throw away the most food?")
        st.altair_chart(charts.hbar(lib.throw_away_by_outlet(f["mart_daily_production"]), "Outlet", "Thrown away (% of cooked)", fmt=",.1f"))
    with right:
        st.subheader("Which ingredients are wasted the most?")
        st.altair_chart(charts.hbar(lib.waste_cost_by_ingredient(f["mart_waste_by_ingredient"]), "Ingredient", "Cost of food thrown away (IDR million)", fmt=",.2f"))

    st.subheader("How much money is thrown away, by outlet and month?")
    heat = lib.waste_cost_outlet_month(f["mart_waste_by_ingredient"])
    st.altair_chart(charts.heatmap(heat, "Month", "Outlet", "IDR million", height=26 * heat["Outlet"].nunique() + 60))

    st.subheader("Why is food thrown away?")
    reasons = lib.waste_by_reason(f["mart_waste_by_ingredient"]).copy()
    reasons["waste_cost"] = reasons["waste_cost"].map("{:,.0f}".format)
    reasons["share_pct"] = reasons["share_pct"].map("{:.1f}%".format)
    reasons = reasons.rename(columns={"waste_cost": "Cost (IDR)", "share_pct": "Share of all waste"})
    reasons.index.name = "Reason"
    st.dataframe(reasons)

# ------------------------------------------------------------ purchases tab
with tab_purchases:
    st.metric("Urgent purchases (share of spending)", f"{k['emergency_share_pct']:.1f}%",
              help="Ingredients bought on short notice because we ran out. Lower is better.")

    left, right = st.columns(2)
    with left:
        st.subheader("How much do we spend on ingredients each month?")
        st.altair_chart(charts.stacked_months(lib.monthly_spend_table(f["mart_purchases_by_ingredient"]), "Month", "Spend (IDR million)", "Type"))
    with right:
        st.subheader("Which ingredients cost the most?")
        st.altair_chart(charts.hbar(lib.spend_by_ingredient(f["mart_purchases_by_ingredient"]), "Ingredient", "Spend (IDR million)", fmt=",.1f"))