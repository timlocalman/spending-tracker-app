import re
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# Load credentials from Streamlit secrets
creds_dict = dict(st.secrets["gcp_service_account"])

# Authenticate
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Pugi_cuQw25_GsGpVQAyzjWuuOFRLmP8yGKaIb6unD0/edit?gid=359073504#gid=359073504")
Spending_Sheet = sheet.worksheet("My Spending Sheet")

def get_today_count():
    today = datetime.now()
    today_str = f"{today.month}/{today.day}/{today.year}"
    all_data = Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])
    today_entries = [row for row in all_data if row.get("DATE") == today_str]
    return len(today_entries)

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

item_category_map = load_item_category_map()

st.title("💸 Spending Tracker Form")

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

    if predicted_category in category_options:
        default_index = category_options.index(predicted_category)
    else:
        default_index = 0

    category = st.selectbox("Item Category", category_options, index=default_index)

    qty = st.number_input("No of Item", min_value=1, step=1)
    amount = st.number_input("Amount Spent", min_value=0.0, step=0.01)

    submitted = st.form_submit_button("Submit")

    if submitted:
        # Regex to match only digits and colons, e.g., 14:30 or 14:30:00
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
            st.success("✅ Transaction submitted successfully!")
