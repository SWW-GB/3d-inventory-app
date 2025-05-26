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
        button[kind="primary"] {
            font-size: 24px !important;
            padding: 20px 40px !important;
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
        st.markdown("<div class='centered-buttons'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🎛️ Filament"):
                st.session_state.selected_type = "filament"
                st.rerun()
        with col2:
            if st.button("🧪 Resin"):
                st.session_state.selected_type = "resin"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
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

    st.markdown("""
    <script>
    document.addEventListener('DOMContentLoaded', function () {
        const draggables = document.querySelectorAll('.draggable');
        const droppables = document.querySelectorAll('.droppable');

        draggables.forEach(el => {
            el.addEventListener('dragstart', e => {
                e.dataTransfer.setData('text/plain', e.target.dataset.id);
            });
        });

        droppables.forEach(area => {
            area.addEventListener('dragover', e => e.preventDefault());
            area.addEventListener('drop', e => {
                e.preventDefault();
                const itemId = e.dataTransfer.getData('text/plain');
                const target = area.getAttribute('data-target');
                fetch(`/?dragged_id=${itemId}&target=${target}`, { method: 'POST' }).then(() => location.reload());
            });
        });
    });
    </script>
    """, unsafe_allow_html=True)

    middle.markdown("## 🟨 Opened")
    middle.markdown("<div class='droppable' data-target='used'>", unsafe_allow_html=True)
    for _, row in opened.iterrows():
        middle.markdown(render_color_block(f"opened_{row['id']}", row["color"], row["count"], row["material"]), unsafe_allow_html=True)
    middle.markdown("</div>", unsafe_allow_html=True)
    middle.markdown("<p style='text-align:center;'>⬇️ Drag here to mark as used</p>", unsafe_allow_html=True)

    right.markdown("## 🟩 Unopened")
    right.markdown("<div class='droppable' data-target='opened'>", unsafe_allow_html=True)
    for _, row in unopened.iterrows():
        right.markdown(render_color_block(f"unopened_{row['id']}", row["color"], row["count"], row["material"]), unsafe_allow_html=True)
    right.markdown("</div>", unsafe_allow_html=True)
    right.markdown("<p style='text-align:center;'>⬅️ Drag to open</p>", unsafe_allow_html=True)

    # Handle drag-and-drop interaction
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
