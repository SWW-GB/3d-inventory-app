import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_sortables import sort_items

# Google Sheets setup
def get_gsheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("3D Printer Inventory").worksheet(sheet_name)
    return sheet

def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(sheet, df):
    sheet.clear()
    sheet.append_row(df.columns.tolist())
    for _, row in df.iterrows():
        sheet.append_row(row.tolist())

def main():
    st.set_page_config(layout="wide")
    st.markdown("""
        <style>
        .material-box {
            display: inline-block;
            border: 1px solid #000;
            width: 100px;
            height: 100px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            margin: 10px;
            padding: 5px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center;'>🧵 3D Printer Inventory Tracker</h1>", unsafe_allow_html=True)

    for key in ["selected_type"]:
        if key not in st.session_state:
            st.session_state[key] = None

    _, top_right = st.columns([8, 1])
    with top_right:
        if st.session_state.selected_type and st.button("🔙 Go Back", key="go_back", help="Return to main menu"):
            st.session_state.selected_type = None
            st.rerun()

    if st.session_state.selected_type is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            col2a, col2b = st.columns(2)
            with col2a:
                if st.button("🎛️ Filament"):
                    st.session_state.selected_type = "filament"
                    st.rerun()
            with col2b:
                if st.button("🧪 Resin"):
                    st.session_state.selected_type = "resin"
                    st.rerun()
        return

    sheet = get_gsheet(st.session_state.selected_type)
    df = load_data(sheet)

    selected_type = st.session_state.selected_type
    filtered_df = df[df["type"] == selected_type].copy() if not df.empty and "type" in df.columns else pd.DataFrame()

    if filtered_df.empty:
        opened = pd.DataFrame()
        unopened = pd.DataFrame()
        st.info("No materials found. Use the form on the left to add some!")
    else:
        opened = filtered_df[filtered_df["status"] == "opened"].reset_index(drop=True)
        unopened = filtered_df[filtered_df["status"] == "unopened"].reset_index(drop=True)

    left, mid_raw, right_raw = st.columns([1, 2, 2])

    with left:
        st.markdown(f"### ➕ Add New {selected_type.title()}")
        with st.form("add_form"):
            material_type = st.selectbox(
                "Type",
                ["PLA", "PETG", "ABS", "Support", "TPU", "PLA-CF", "PETG-CF"] if selected_type == "filament" else ["basic", "tough", "rigid", "flexible"],
                index=0
            )
            color = st.text_input("Color")
            count = st.number_input("Quantity", min_value=1, step=1)
            submitted = st.form_submit_button("Add Material")
            if submitted:
                match = df[(df["type"] == selected_type) & (df["material"] == material_type) & (df["color"] == color) & (df["status"] == "unopened")]
                if not match.empty:
                    df.at[match.index[0], "count"] += count
                else:
                    new_entry = {
                        "id": len(df) + 1,
                        "type": selected_type,
                        "material": material_type,
                        "brand": "",
                        "color": color,
                        "status": "unopened",
                        "count": count,
                        "notes": ""
                    }
                    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(sheet, df)
                st.success("Material added successfully.")
                st.rerun()

    def format_box(row):
        return f"<div class='material-box' style='background:{row['color']}'>{row['material']}<br>{row['count']}<br>{row['color']}</div>"

    with mid_raw:
        st.markdown("<h3>🟨 Opened</h3>", unsafe_allow_html=True)
        opened_html = [format_box(row) for _, row in opened.iterrows()]
        sort_items("opened_zone", opened_html)

    with right_raw:
        st.markdown("<h3>🟩 Unopened</h3>", unsafe_allow_html=True)
        unopened_html = [format_box(row) for _, row in unopened.iterrows()]
        sort_items("unopened_zone", unopened_html)

    st.markdown("<h3>🗑️ Used</h3>", unsafe_allow_html=True)
    used_html = []
    sort_items("used_zone", used_html)

    st.warning("Note: drag-to-update is visual only — backend actions must be added via tracking logic")

if __name__ == "__main__":
    main()
