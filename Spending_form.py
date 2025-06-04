import re
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import altair as alt

# Load credentials from Streamlit secrets
creds_dict = dict(st.secrets["gcp_service_account"])

# Authenticate
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Pugi_cuQw25_GsGpVQAyzjWuuOFRLmP8yGKaIb6unD0/edit?gid=359073504#gid=359073504")
Spending_Sheet = sheet.worksheet("My Spending Sheet")

# --- HELPER FUNCTIONS ---
def get_today_count():
    today = datetime.now()
    today_str = f"{today.month}/{today.day}/{today.year}"
    all_data = Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])
    today_entries = [row for row in all_data if row.get("DATE") == today_str]
    return len(today_entries)

def get_total_amount_by_period(filter_key, filter_value):
    all_data = Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])
    total = 0.0
    for row in all_data:
        if row.get(filter_key) == filter_value:
            category = row.get("ITEM CATEGORY", "").lower()
            if category not in ["savings", "income"]:
                try:
                    total += float(row.get("Amount Spent", 0))
                except ValueError:
                    continue
    return total

def get_today_total_amount():
    today_str = f"{datetime.now().month}/{datetime.now().day}/{datetime.now().year}"
    return get_total_amount_by_period("DATE", today_str)

def get_weekly_total_amount():
    monday_dt = datetime.now() - timedelta(days=datetime.now().weekday())
    week_str = f"{monday_dt.day}-{monday_dt.strftime('%b')}"
    return get_total_amount_by_period("WEEK", week_str)

def get_monthly_total_amount():
    month_str = datetime.now().strftime("%B %Y")
    return get_total_amount_by_period("MONTH", month_str)

@st.cache_data(ttl=3600)
def load_item_category_map():
    all_data = Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])
    item_category_map = {}
    for row in all_data:
        item_name = row.get("ITEM", "").strip().lower()
        category = row.get("ITEM CATEGORY", "").strip()
        if item_name and category:
            item_category_map[item_name] = category
    return item_category_map

@st.cache_data(ttl=600)
def load_all_data():
    return Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])

# Load data
item_category_map = load_item_category_map()
all_data = load_all_data()

# --- UI ---
st.title("💸 Spending Tracker Form")

# Show spending summaries
total_today = get_today_total_amount()
total_week = get_weekly_total_amount()
total_month = get_monthly_total_amount()

col1, col2, col3 = st.columns(3)
col1.metric(label="🗓️ Total Spent Today", value=f"₦{total_today:,.2f}")
col2.metric(label="📅 Total This Week", value=f"₦{total_week:,.2f}")
col3.metric(label="📆 Total This Month", value=f"₦{total_month:,.2f}")

# --- FORM ---
with st.form("entry_form", clear_on_submit=True):
    st.write("### Enter New Transaction")

    selected_date = st.date_input("Date", datetime.today())
    date = f"{selected_date.month}/{selected_date.day}/{selected_date.year}"

    time_input = st.text_input("Time (only digits and colons allowed, e.g. 14:30 or 14:30:00)", value="")

    item = st.text_input("Item").strip()

    predicted_category = item_category_map.get(item.lower(), "Select Category")

    category_options = [
        "Select Category",
        "Bet", "Bill", "Data", "Food", "Foodstuff", "Money", "Object", "Snacks",
        "transfer", "income", "Airtime", "transport", "Savings"
    ]

    default_index = category_options.index(predicted_category) if predicted_category in category_options else 0
    category = st.selectbox("Item Category", category_options, index=default_index)

    qty = st.number_input("No of Item", min_value=1, step=1)
    amount = st.number_input("Amount Spent", min_value=0.0, step=0.01)

    submitted = st.form_submit_button("Submit")

    if submitted:
        if not re.fullmatch(r"[0-9:]+", time_input):
            st.warning("⚠️ Time field must contain only digits and colons (e.g. 14:30 or 14:30:00).")
        elif category == "Select Category":
            st.warning("⚠️ Please select a valid item category before submitting.")
        elif not item:
            st.warning("⚠️ Please enter an item name.")
        else:
            transaction_id = get_today_count() + 1

            today_dt = datetime.now()
            monday_dt = today_dt - timedelta(days=today_dt.weekday())
            monday_of_week = f"{monday_dt.day}-{monday_dt.strftime('%b')}"
            month_str = today_dt.strftime("%B %Y")

            row = [
                date,
                transaction_id,
                time_input,
                item,
                category,
                qty,
                amount,
                monday_of_week,
                month_str
            ]

            Spending_Sheet.append_row(row)
            st.cache_data.clear()  # <-- Clear cache so data reloads
            st.success("✅ Transaction submitted successfully!")

# --- VISUALIZATIONS ---
st.markdown("## 📊 Spending Breakdown")

# Create DataFrame and clean
df = pd.DataFrame(all_data)
df["Amount Spent"] = pd.to_numeric(df["Amount Spent"], errors="coerce")

# Filter out "savings" and "income"
df = df[df["ITEM CATEGORY"].str.lower().isin([
    "bet", "bill", "data", "food", "foodstuff", "money", "object", "snacks",
    "transfer", "airtime", "transport"
])]

# Prepare daily line chart for current week
today = datetime.now()
monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)

# Convert DATE to datetime objects for filtering
df["DATE_dt"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y", errors='coerce')
df_week = df[(df["DATE_dt"] >= monday) & (df["DATE_dt"] <= today)]

daily_summary = df_week.groupby("DATE_dt", as_index=False)["Amount Spent"].sum()
daily_summary["Day"] = daily_summary["DATE_dt"].dt.strftime("%a")

line_chart = alt.Chart(daily_summary).mark_line(point=True).encode(
    x=alt.X("Day:N", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
    y="Amount Spent:Q"
).properties(
    title="📈 Daily Spending This Week",
    height=300
)
st.altair_chart(line_chart, use_container_width=True)

# --- Daily Pie Chart ---
today_str = f"{today.month}/{today.day}/{today.year}"
df_today = df[df["DATE"] == today_str]
item_today_summary = df_today.groupby("ITEM", as_index=False)["Amount Spent"].sum()

if not item_today_summary.empty:
    pie_chart = alt.Chart(item_today_summary).mark_arc(innerRadius=50).encode(
        theta="Amount Spent:Q",
        color="ITEM:N",
        tooltip=["ITEM", "Amount Spent"]
    ).properties(
        title="🥧 Today's Spending by Item",
        height=400
    )
    st.altair_chart(pie_chart, use_container_width=True)
else:
    st.info("ℹ️ No spending recorded today (excluding Savings/Income).")