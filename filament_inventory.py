import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_dnd import dnd_area, dnd_label

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
    return df[df["count"] > 0]

def color_block(color, count, label):
    return dnd_label(
        label,
        children=f"<div style='background:{color};width:100px;height:100px;border-radius:10px;text-align:center;line-height:100px;font-weight:bold;margin:5px;'>{count}</div>",
        height=110,
    )

def main():
    st.set_page_config(layout="wide")
    st.title("🧵 3D Printer Inventory Tracker")

    sheet = get_gsheet()
    df = load_data(sheet)

    if "selected_type" not in st.session_state:
        st.session_state.selected_type = None

    top_left, top_right = st.columns([8, 1])
    with top_right:
        if st.session_state.selected_type is not None and st.button("🔙 Go Back"):
            st.session_state.selected_type = None
            st.rerun()

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
        st.markdown(f"### ➕ Add New {selected_type.title()}")
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

    with right:
        st.markdown("## 🟩 Unopened")
        with dnd_area("Unopened", background_color="#e0ffe0") as unopened_area:
            for _, row in unopened.iterrows():
                label = f"unopened_{row['id']}"
                color_block(row["color"], row["count"], label)

    with middle:
        st.markdown("## 🟨 Opened")
        with dnd_area("Opened", background_color="#ffffcc") as opened_area:
            for _, row in opened.iterrows():
                label = f"opened_{row['id']}"
                color_block(row["color"], row["count"], label)

        st.markdown("## 🗑️ Used")
        with dnd_area("Used", background_color="#f0f0f0") as used_area:
            st.write("Drop opened items here to mark them as used.")

    # Handle drop logic
    if unopened_area and unopened_area.startswith("unopened_"):
        item_id = int(unopened_area.split("_")[1])
        row = unopened[unopened["id"] == item_id].iloc[0]
        df = update_quantity(df, row["index"], -1)
        match = df[(df["type"] == row["type"]) & (df["material"] == row["material"]) & (df["color"] == row["color"]) & (df["status"] == "opened")]
        if not match.empty:
            df.at[match.index[0], "count"] += 1
        else:
            new_row = row.copy()
            new_row["status"] = "opened"
            new_row["count"] = 1
            new_row["id"] = len(df) + 1
            df = pd.concat([df, pd.DataFrame([new_row.drop(labels=["index"])])], ignore_index=True)
        save_data(sheet, df)
        st.rerun()

    if used_area and used_area.startswith("opened_"):
        item_id = int(used_area.split("_")[1])
        row = opened[opened["id"] == item_id].iloc[0]
        df = update_quantity(df, row["index"], -1)
        save_data(sheet, df)
        st.rerun()

if __name__ == "__main__":
    main()
