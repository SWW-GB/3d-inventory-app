import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

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

def main():
    st.title("🧵 3D Printer Filament & Resin Tracker")
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
    st.subheader(f"📦 Current Inventory: {selected_type.title()}")
    filtered_df = df[df["type"] == selected_type]

    if st.button(f"➕ Add New {selected_type.title()}"):
        with st.form("add_form"):
            new_entry = {
                "id": len(df) + 1,
                "type": selected_type,
                "material": st.text_input("Material"),
                "brand": st.text_input("Brand"),
                "color": st.text_input("Color"),
                "status": st.selectbox("Status", ["unopened", "opened"]),
                "count": st.number_input("Count", min_value=1, step=1),
                "notes": st.text_input("Notes")
            }
            submitted = st.form_submit_button("Add Material")
            if submitted:
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(sheet, df)
                st.success("Material added successfully.")
                st.rerun()

    # Sections
    opened = filtered_df[filtered_df["status"] == "opened"].reset_index()
    unopened = filtered_df[filtered_df["status"] == "unopened"].reset_index()

    st.markdown("## 🟨 Opened")
    for _, row in opened.iterrows():
        with st.container():
            st.markdown(f"**{row['material']} ({row['color']}) - {row['brand']}**: {row['count']}x")
            if st.button(f"✅ Mark One Used - ID {row['id']}", key=f"used_{row['id']}"):
                df = update_quantity(df, row["index"], -1)
                save_data(sheet, df)
                st.rerun()

    st.markdown("## 🟩 Unopened")
    for _, row in unopened.iterrows():
        with st.container():
            st.markdown(f"**{row['material']} ({row['color']}) - {row['brand']}**: {row['count']}x")
            if st.button(f"📤 Open One - ID {row['id']}", key=f"open_{row['id']}"):
                # Reduce unopened
                df = update_quantity(df, row["index"], -1)
                # Find match to add to opened
                match = df[
                    (df["type"] == row["type"]) &
                    (df["material"] == row["material"]) &
                    (df["brand"] == row["brand"]) &
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

if __name__ == "__main__":
    main()
