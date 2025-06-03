import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import copy
from datetime import datetime, timedelta

# Make a copy of the service account info from secrets
creds_dict = copy.deepcopy(st.secrets["gcp_service_account"])

# Fix private key newlines
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

# Define the scopes needed
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Create credentials object
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

# Authorize gspread with these credentials
gc = gspread.authorize(credentials)

# Open your Google Sheet and worksheet
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Pugi_cuQw25_GsGpVQAyzjWuuOFRLmP8yGKaIb6unD0/edit?gid=359073504#gid=359073504")
Spending_Sheet = sheet.worksheet("My Spending Sheet")

# --- HELPER FUNCTION TO GET TODAY'S TRANSACTION COUNT ---
def get_today_count():
    today = datetime.now()
    today_str = f"{today.month}/{today.day}/{today.year}"
    all_data = Spending_Sheet.get_all_records(expected_headers=[
        "DATE", "No", "TIME", "ITEM", "ITEM CATEGORY", "No of ITEM", "Amount Spent", "WEEK", "MONTH"
    ])
    today_entries = [row for row in all_data if row.get("DATE") == today_str]
    return len(today_entries)

# --- HELPER FUNCTION TO BUILD ITEM->CATEGORY MAPPING ---
@st.cache_data(ttl=3600)  # cache for 1 hour
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

# --- STREAMLIT FORM ---
st.title("💸 Spending Tracker Form")

with st.form("entry_form", clear_on_submit=True):
    st.write("### Enter New Transaction")

    selected_date = st.date_input("Date", datetime.today())
    date = f"{selected_date.month}/{selected_date.day}/{selected_date.year}"
    time = st.time_input("Time", datetime.now().time()).strftime("%I:%M:%S %p")

    item = st.text_input("Item").strip()

    predicted_category = item_category_map.get(item.lower(), "Select Category")

    category_options = [
        "Select Category", "Bet", "Bill", "Data", "Food", "Foodstuff", "Money", "Object",
        "Snacks", "transfer", "income", "Airtime", "transport", "Savings"
    ]

    default_index = category_options.index(predicted_category) if predicted_category in category_options else 0

    category = st.selectbox("Item Category", category_options, index=default_index)

    qty = st.number_input("No of Item", min_value=1, step=1)
    amount = st.number_input("Amount Spent", min_value=0.0, step=0.01)

    submitted = st.form_submit_button("Submit")

    if submitted:
        if category == "Select Category":
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
                time,
                item,
                category,
                qty,
                amount,
                monday_of_week,
                month_str
            ]

            Spending_Sheet.append_row(row)
            st.success("✅ Transaction submitted successfully!")