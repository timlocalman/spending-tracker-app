import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
from datetime import datetime, timedelta
import json

# --- LOAD SECRETS ---
creds_dict = dict(st.secrets["gcp_service_account"])

# --- AUTHENTICATE GOOGLE SHEETS ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)

sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Pugi_cuQw25_GsGpVQAyzjWuuOFRLmP8yGKaIb6unD0/edit?gid=359073504#gid=359073504")
Spending_Sheet = sheet.worksheet("My Spending Sheet")

# --- GET LOCAL TIME ---
local_tz = pytz.timezone("Africa/Lagos")
now = datetime.now(pytz.utc).astimezone(local_tz)

# --- HELPER: GET TODAY COUNT ---
def get_today_count():
    today_str = now.strftime("%-m/%-d/%Y")
    all_data = Spending_Sheet.get_all_records()
    today_entries = [row for row in all_data if row.get("DATE") == today_str]
    return len(today_entries)

# --- HELPER: LOAD ITEM-CATEGORY MAPPING ---
@st.cache_data(ttl=3600)
def load_item_category_map():
    all_data = Spending_Sheet.get_all_records()
    item_category_map = {}
    for row in all_data:
        item = row.get("ITEM", "").strip().lower()
        category = row.get("ITEM CATEGORY", "").strip()
        if item and category:
            item_category_map[item] = category
    return item_category_map

item_category_map = load_item_category_map()

# --- STREAMLIT FORM ---
st.title("💸 Spending Tracker Form")

with st.form("entry_form", clear_on_submit=True):
    st.write("### Enter New Transaction")

    # Date input
    selected_date = st.date_input("Date", now.date())
    date_str = f"{selected_date.month}/{selected_date.day}/{selected_date.year}"

    # Text-based time input with default
    raw_time = st.text_input("Time (e.g., 02:30 PM)", value=now.strftime("%I:%M %p"))
    try:
        parsed_time = datetime.strptime(raw_time, "%I:%M %p")
        time_str = parsed_time.strftime("%I:%M:%S %p")
    except ValueError:
        time_str = None
        st.error("⚠️ Enter time in format like '02:45 PM'")

    item = st.text_input("Item").strip()

    # Predict category
    predicted_category = item_category_map.get(item.lower(), "Select Category")
    category_options = [
        "Select Category", "Bet", "Bill", "Data", "Food", "Foodstuff", "Money",
        "Object", "Snacks", "transfer", "income", "Airtime", "transport", "Savings"
    ]
    default_index = category_options.index(predicted_category) if predicted_category in category_options else 0
    category = st.selectbox("Item Category", category_options, index=default_index)

    qty = st.number_input("No of Item", min_value=1, step=1)
    amount = st.number_input("Amount Spent", min_value=0.0, step=0.01)

    submitted = st.form_submit_button("Submit")

    if submitted:
        if not time_str:
            st.warning("Please enter a valid time.")
        elif category == "Select Category":
            st.warning("Please select a valid item category.")
        elif not item:
            st.warning("Please enter an item name.")
        else:
            transaction_id = get_today_count() + 1
            monday_dt = now - timedelta(days=now.weekday())
            week_str = f"{monday_dt.day}-{monday_dt.strftime('%b')}"
            month_str = now.strftime("%B %Y")

            row = [
                date_str,
                transaction_id,
                time_str,
                item,
                category,
                qty,
                amount,
                week_str,
                month_str
            ]

            Spending_Sheet.append_row(row)
            st.success("✅ Transaction submitted successfully!")