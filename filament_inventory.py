import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit.components.v1 import html

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

def render_color_block(item_id, color, count, material):
    return f"""
    <div class='draggable' draggable='true' data-id='{item_id}' style='background:{color};border:1px solid #000;width:100px;height:100px;border-radius:10px;text-align:center;font-weight:bold;margin:5px;padding:5px;'>
        <div style='font-size:12px;'>{material}</div>
        <div style='line-height:60px;font-size:24px;'>{count}</div>
    </div>
    """

def main():
    st.set_page_config(layout="wide")
    st.markdown("""
        <style>
        .centered-buttons div[data-testid="column"] {
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .stButton > button {
            font-size: 32px !important;
            padding: 30px 60px !important;
        }
        .droppable {
            min-height: 200px;
            border: 2px dashed #ccc;
            padding: 10px;
            margin-bottom: 20px;
        }
        .draggable {
            cursor: grab;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center;'>🧵 3D Printer Inventory Tracker</h1>", unsafe_allow_html=True)

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
        st.markdown("""
        <div style='display: flex; justify-content: center; align-items: center; gap: 2rem;'>
            <form action='' method='post'>
                <button name='type' value='filament' style='font-size: 32px; padding: 30px 60px;'>🎛️ Filament</button>
            </form>
            <form action='' method='post'>
                <button name='type' value='resin' style='font-size: 32px; padding: 30px 60px;'>🧪 Resin</button>
            </form>
        </div>
    """, unsafe_allow_html=True)

        if st.query_params.get("type"):
            st.session_state.selected_type = st.query_params["type"]
            st.query_params.clear()
            st.rerun()
        return

    selected_type = st.session_state.selected_type
    filtered_df = df[df["type"] == selected_type].copy()
    opened = filtered_df[filtered_df["status"] == "opened"].reset_index()
    unopened = filtered_df[filtered_df["status"] == "unopened"].reset_index()

    st.markdown("""
    <script>
    window.addEventListener('message', e => {
        const [id, target] = e.data.split('|');
        const url = new URL(window.location.href);
        url.searchParams.set('dragged_id', id);
        url.searchParams.set('target', target);
        window.location.href = url.toString();
    });
    </script>
    """, unsafe_allow_html=True)

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

    middle.markdown("## 🟨 Opened")
    html("""<div class='droppable' ondrop="window.parent.postMessage(event.dataTransfer.getData('text') + '|used', '*')" ondragover="event.preventDefault()">""")
    for _, row in opened.iterrows():
        middle.markdown(render_color_block(f"opened_{row['id']}", row["color"], row["count"], row["material"]), unsafe_allow_html=True)
    html("""</div><p style='text-align:center;'>⬇️ Drag here to mark as used</p>""")

    right.markdown("## 🟩 Unopened")
    html("""<div class='droppable' ondrop="window.parent.postMessage(event.dataTransfer.getData('text') + '|opened', '*')" ondragover="event.preventDefault()">""")
    for _, row in unopened.iterrows():
        right.markdown(render_color_block(f"unopened_{row['id']}", row["color"], row["count"], row["material"]), unsafe_allow_html=True)
    html("""</div><p style='text-align:center;'>⬅️ Drag to open</p>""")

    query_params = st.query_params
    dragged_id = query_params.get("dragged_id", [None])[0]
    target = query_params.get("target", [None])[0]

    if dragged_id and target:
        if dragged_id.startswith("unopened_") and target == "opened":
            item_id = int(dragged_id.split("_")[1])
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
            st.query_params.clear()
            st.rerun()

        elif dragged_id.startswith("opened_") and target == "used":
            item_id = int(dragged_id.split("_")[1])
            row = opened[opened["id"] == item_id].iloc[0]
            df = update_quantity(df, row["index"], -1)
            save_data(sheet, df)
            st.query_params.clear()
            st.rerun()

if __name__ == "__main__":
    main()
