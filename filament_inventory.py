import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_sortables import sort_items

# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("3D Printer Inventory").worksheet("inventory")
    return sheet

def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(sheet, df):
    sheet.clear()
    sheet.append_row(df.columns.tolist())
    for _, row in df.iterrows():
        sheet.append_row(row.tolist())

def update_quantity(df, index, delta):
    df.at[index, "count"] += delta
    return df[df["count"] > 0]  # Remove if count becomes 0

def color_block(color, count):
    return f"""
    <div style='background:{color};width:100px;height:100px;border-radius:10px;text-align:center;line-height:100px;font-weight:bold;margin:5px;'>
        {count}
    </div>
    """

def main():
    st.set_page_config(layout="wide")
    st.title("🧵 3D Printer Inventory Tracker")

    sheet = get_gsheet()
    df = load_data(sheet)

    if "selected_type" not in st.session_state:
        st.session_state.selected_type = None

    if st.session_state.selected_type is None:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎛️ Filament"):
                st.session_state.selected_type = "filament"
                st.rerun()
        with col2:
            if st.button("🧪 Resin"):
                st.session_state.selected_type = "resin"
                st.rerun()
        return

    selected_type = st.session_state.selected_type
    filtered_df = df[df["type"] == selected_type].copy()
    opened = filtered_df[filtered_df["status"] == "opened"].reset_index()
    unopened = filtered_df[filtered_df["status"] == "unopened"].reset_index()

    left, middle, right = st.columns([1, 2, 2])

    with left:
        if st.button(f"➕ Add New {selected_type.title()}"):
            with st.form("add_form"):
                if selected_type == "filament":
                    f_type = st.selectbox("Type", ["PLA", "PETG", "ABS", "Support", "TPU", "PLA-CF", "PETG-CF"], index=0)
                else:
                    f_type = st.selectbox("Type", ["basic", "tough", "rigid", "flexible"], index=0)
                color = st.text_input("Color")
                count = st.number_input("Quantity", min_value=1, step=1)
                submitted = st.form_submit_button("Add Material")
                if submitted:
                    new_entry = {
                        "id": len(df) + 1,
                        "type": selected_type,
                        "material": f_type,
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

    with middle:
        st.markdown("## 🟨 Opened")
        for _, row in opened.iterrows():
            st.markdown(color_block(row["color"], row["count"]), unsafe_allow_html=True)
            if st.button(f"🗑️ Mark One Used - ID {row['id']}", key=f"used_{row['id']}"):
                df = update_quantity(df, row["index"], -1)
                save_data(sheet, df)
                st.rerun()

    with right:
        st.markdown("## 🟩 Unopened")
        for _, row in unopened.iterrows():
            st.markdown(color_block(row["color"], row["count"]), unsafe_allow_html=True)
            if st.button(f"📤 Open One - ID {row['id']}", key=f"open_{row['id']}"):
                df = update_quantity(df, row["index"], -1)
                match = df[
                    (df["type"] == row["type"]) &
                    (df["material"] == row["material"]) &
                    (df["color"] == row["color"]) &
                    (df["status"] == "opened")
                ]
                if not match.empty:
                    idx = match.index[0]
                    df.at[idx, "count"] += 1
                else:
                    new_row = row.copy()
                    new_row["status"] = "opened"
                    new_row["count"] = 1
                    new_row["id"] = len(df) + 1
                    df = pd.concat([df, pd.DataFrame([new_row.drop(labels=["index"])])], ignore_index=True)
                save_data(sheet, df)
                st.rerun()

    st.markdown("""
        <style>
        div[role="button"] button {
            margin: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("🔙 Go Back"):
        st.session_state.selected_type = None
        st.rerun()

if __name__ == "__main__":
    main()

