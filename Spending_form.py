import re
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import altair as alt

# --- CONFIG ---
st.set_page_config(page_title="Spending Tracker", layout="wide")

# --- CATEGORY BUDGETS ---
category_budgets = {
    "Bet": 3000,
    "Bill": 35000,
    "Data": 11000,
    "Food": 40000,
    "Foodstuff": 150000,
    "Money": 10000,
    "Object": 50000,
    "Snacks": 60000,
    "transfer": 300000,
    "income": 250000,
    "Airtime": 1000,
    "transport": 70000,
    "Savings": 400000,
}

# --- GOOGLE SHEETS AUTH ---
creds_dict = dict(st.secrets["gcp_service_account"])
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Pugi_cuQw25_GsGpVQAyzjWuuOFRLmP8yGKaIb6unD0/edit?gid=359073504#gid=359073504")
Spending_Sheet = sheet.worksheet("My Spending Sheet")

# --- DATA HELPERS ---
def get_today_count():
    today = datetime.now()
    today_str = f"{today.month}/{today.day}/{today.year}"
    all_data = Spending_Sheet.get_all_records(expected_headers=["DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"])
    return len([row for row in all_data if row.get("DATE") == today_str])

def get_total_amount_by_period(key, value):
    all_data = Spending_Sheet.get_all_records(expected_headers=["DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"])
    return sum(float(row.get("Amount Spent", 0)) for row in all_data if row.get(key) == value and row.get("ITEM CATEGORY", "").lower() not in ["savings", "income"])

def get_today_total_amount():
    return get_total_amount_by_period("DATE", f"{datetime.now().month}/{datetime.now().day}/{datetime.now().year}")

def get_weekly_total_amount():
    week_str = f"{(datetime.now() - timedelta(days=datetime.now().weekday())).day}-{datetime.now().strftime('%b')}"
    return get_total_amount_by_period("WEEK", week_str)

def get_monthly_total_amount():
    return get_total_amount_by_period("MONTH", datetime.now().strftime("%B %Y"))

@st.cache_data(ttl=3600)
def load_item_category_map():
    all_data = Spending_Sheet.get_all_records(expected_headers=["DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"])
    return {row["ITEM"].strip().lower(): row["ITEM CATEGORY"].strip() for row in all_data if row["ITEM"] and row["ITEM CATEGORY"]}

@st.cache_data(ttl=600)
def load_all_data():
    return Spending_Sheet.get_all_records(expected_headers=["DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"])

# --- LOAD DATA ---
item_category_map = load_item_category_map()
all_data = load_all_data()
df = pd.DataFrame(all_data)
df["Amount Spent"] = pd.to_numeric(df["Amount Spent"], errors="coerce")

# --- Recommendation: Items likely to buy today based on past weekday purchases ---
def recommend_items_for_today(df, top_n=5):
    if df.empty:
        return []
    if "DATE" not in df or "ITEM" not in df:
        return []
    
    # Convert DATE to datetime
    df["DATE_dt"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y", errors='coerce')
    # Get today's weekday string
    today_weekday = datetime.now().strftime("%A")
    # Add weekday column
    df["Weekday"] = df["DATE_dt"].dt.day_name()
    # Filter to transactions on same weekday
    df_today_weekday = df[df["Weekday"] == today_weekday]
    # Count items frequency
    item_counts = df_today_weekday["ITEM"].str.strip().value_counts()
    # Return top N items as list
    return item_counts.head(top_n).index.tolist()

likely_items = recommend_items_for_today(df)

# --- METRICS ---
st.title("💸 Spending Tracker")
with st.container():
    col1, col2, col3 = st.columns(3)
    col1.metric("🗓️ Today", f"₦{get_today_total_amount():,.2f}")
    col2.metric("📅 This Week", f"₦{get_weekly_total_amount():,.2f}")
    col3.metric("📆 This Month", f"₦{get_monthly_total_amount():,.2f}")
st.markdown("---")  # Divider line

# --- TOTAL PROGRESS ---
total_month = get_monthly_total_amount()
total_budget = sum(b for k, b in category_budgets.items() if k.lower() not in ["savings", "income"])
percent_used = total_month / total_budget if total_budget > 0 else 0

st.markdown("### 🏁 Monthly Budget Usage")
st.progress(min(percent_used, 1.0), text=f"₦{total_month:,.0f} of ₦{total_budget:,.0f} used ({percent_used*100:.1f}%)")
st.markdown("---")  # Divider line

# --- Show recommendations ---
if likely_items:
    st.markdown("### 🛒 Items You Might Buy Today (based on past purchases)")
    cols = st.columns(len(likely_items))
    for idx, recommended_item in enumerate(likely_items):
        if cols[idx].button(recommended_item):
            st.session_state["prefill_item"] = recommended_item
st.markdown("---")  # Divider line
# --- INPUT FORM ---
with st.form("entry_form", clear_on_submit=True):
    st.markdown("### ✍️ Add New Transaction")

    selected_date = st.date_input("📆 Date", datetime.today())
    time_input = st.text_input("⏰ Time (e.g. 14:30 or 14:30:00)")

    # Use prefill if user clicked recommended button
    prefill_item = st.session_state.get("prefill_item", "")
    item = st.text_input("🛒 Item", value=prefill_item).strip()

    predicted_category = item_category_map.get(item.lower(), "Select Category")
    category_options = ["Select Category"] + list(category_budgets.keys())
    default_index = category_options.index(predicted_category) if predicted_category in category_options else 0
    category = st.selectbox("📂 Category", category_options, index=default_index)

    col1, col2 = st.columns(2)
    with col1:
        qty = st.number_input("🔢 Quantity", min_value=1, step=1)
    with col2:
        amount = st.number_input("💸 Amount", min_value=0.0, step=0.01)

    if st.form_submit_button("✅ Submit"):
        if not re.fullmatch(r"[0-9:]+", time_input):
            st.warning("⚠️ Time must contain only digits and colons (e.g. 14:30).")
        elif category == "Select Category":
            st.warning("⚠️ Please select a valid category.")
        elif not item:
            st.warning("⚠️ Item name is required.")
        else:
            transaction_id = get_today_count() + 1
            monday_str = f"{(datetime.now() - timedelta(days=datetime.now().weekday())).day}-{datetime.now().strftime('%b')}"
            month_str = datetime.now().strftime("%B %Y")

            new_row = [
                f"{selected_date.month}/{selected_date.day}/{selected_date.year}",
                transaction_id,
                time_input,
                item,
                category,
                qty,
                amount,
                monday_str,
                month_str
            ]

            Spending_Sheet.append_row(new_row)
            st.cache_data.clear()
            st.success("✅ Transaction submitted!")
            # Clear prefill after submit
            if "prefill_item" in st.session_state:
                del st.session_state["prefill_item"]
st.markdown("---")  # Divider line
# --- FILTERED DATAFRAME FOR VISUALS ---
df = df[df["ITEM CATEGORY"].str.lower().isin([c.lower() for c in category_budgets if c.lower() not in ["savings", "income"]])]
df["DATE_dt"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y", errors='coerce')
# --- TODAY'S TRANSACTIONS TABLE ---
st.markdown("### 📋 Today's Transactions")

today_str = f"{datetime.now().month}/{datetime.now().day}/{datetime.now().year}"
df_today = df[df["DATE"] == today_str]

if not df_today.empty:
    st.dataframe(
        df_today[["TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("ℹ️ No transactions recorded yet today.")
st.markdown("---")  # Divider line
st.markdown("### 📅 Last Time Each Item Was Bought (by Category)")

# Dropdown to filter by category
all_categories = sorted(df["ITEM CATEGORY"].dropna().unique())
selected_cat = st.selectbox("📂 Select Category", all_categories)

if selected_cat:
    df_cat = df[df["ITEM CATEGORY"] == selected_cat]
    # Get last purchase date per item
    last_purchase = df_cat.groupby("ITEM")["DATE_dt"].max().reset_index()
    last_purchase["Last Bought"] = last_purchase["DATE_dt"].dt.strftime("%B %d")
    last_purchase = last_purchase[["ITEM", "Last Bought"]].rename(columns={"ITEM": "Item"})

    if not last_purchase.empty:
        st.dataframe(last_purchase.sort_values("Last Bought", ascending=False), use_container_width=True)
    else:
        st.info("ℹ️ No purchases found in this category.")
st.markdown("---")  # Divider line
# --- DROPDOWN TO SELECT CHART VIEW ---
chart_view = st.selectbox("📊 Select Chart to Display", ["Weekly Spending", "Today's Breakdown", "Category Progress"])

# --- WEEKLY BAR CHART ---
if chart_view == "Weekly Spending":
    week_start = datetime.now() - timedelta(days=datetime.now().weekday())
    df_week = df[df["DATE_dt"].between(week_start, datetime.now())]
    if not df_week.empty:
        chart_data = df_week.groupby("DATE_dt")["Amount Spent"].sum().reset_index()
        chart_data["Day"] = chart_data["DATE_dt"].dt.strftime("%a")
        bar_chart = alt.Chart(chart_data).mark_bar().encode(
            x=alt.X("Day:N", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            y="Amount Spent:Q",
            tooltip=["Day", "Amount Spent"]
        ).properties(title="Daily Spending", height=250)
        st.altair_chart(bar_chart, use_container_width=True)
    else:
        st.info("ℹ️ No data for this week yet.")

# --- TODAY PIE CHART ---
elif chart_view == "Today's Breakdown":
    today_str = f"{datetime.now().month}/{datetime.now().day}/{datetime.now().year}"
    df_today = df[df["DATE"] == today_str]
    pie_data = df_today.groupby("ITEM")["Amount Spent"].sum().reset_index()
    if not pie_data.empty:
        pie_chart = alt.Chart(pie_data).mark_arc(innerRadius=50).encode(
            theta="Amount Spent:Q",
            color="ITEM:N",
            tooltip=["ITEM", "Amount Spent"]
        ).properties(height=350)
        st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.info("ℹ️ No spending recorded today.")

# --- CATEGORY PROGRESS ---
elif chart_view == "Category Progress":
    st.markdown("### 📂 Category Budget Tracking")
    df_month = df[df["MONTH"] == datetime.now().strftime("%B %Y")]
    cat_month = df_month.groupby("ITEM CATEGORY")["Amount Spent"].sum().reset_index()

    for cat, budget in category_budgets.items():
        if cat.lower() in ["savings", "income"]:
            continue
        spent = cat_month.loc[cat_month["ITEM CATEGORY"].str.lower() == cat.lower(), "Amount Spent"].sum()
        percent = spent / budget if budget > 0 else 0
        st.markdown(f"**{cat}** — ₦{spent:,.0f} / ₦{budget:,.0f} ({percent*100:.1f}%)")
        st.progress(min(percent, 1.0))
