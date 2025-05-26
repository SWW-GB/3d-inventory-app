import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    import json
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

def main():
    st.title("🧵 3D Printer Filament & Resin Tracker")
    sheet = get_gsheet()
    df = load_data(sheet)

    st.subheader("📦 Current Inventory")
    st.dataframe(df)

    with st.form("add_form"):
        st.write("### ➕ Add New Material")
        new_entry = {
            "id": len(df) + 1,
            "type": st.selectbox("Type", ["filament", "resin"]),
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

    st.subheader("🔁 Use an Unopened Material")
    unopened = df[(df["status"] == "unopened") & (df["count"] > 0)]

    if not unopened.empty:
        selection = st.selectbox(
            "Select unopened material:",
            unopened.index.tolist(),
            format_func=lambda i: f"{unopened.loc[i, 'material']} ({unopened.loc[i, 'color']}) [{unopened.loc[i, 'brand']}] - {unopened.loc[i, 'count']}x"
        )
        if st.button("Mark One as Opened"):
            selected = unopened.loc[selection]
            # Reduce unopened count
            df.at[selection, "count"] -= 1

            # Check for existing opened entry
            match = df[
                (df["type"] == selected["type"]) &
                (df["material"] == selected["material"]) &
                (df["brand"] == selected["brand"]) &
                (df["color"] == selected["color"]) &
                (df["status"] == "opened")
            ]

            if not match.empty:
                idx = match.index[0]
                df.at[idx, "count"] += 1
            else:
                new_opened = selected.copy()
                new_opened["status"] = "opened"
                new_opened["count"] = 1
                new_opened["id"] = len(df) + 1
                df = pd.concat([df, pd.DataFrame([new_opened])], ignore_index=True)

            save_data(sheet, df)
            st.success("Moved 1 unopened → opened.")
            st.rerun()
    else:
        st.info("No unopened materials available.")

if __name__ == "__main__":
    main()

