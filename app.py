# app.py

import streamlit as st
import pandas as pd
from engine import BehaviorTracker
from datetime import datetime
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# --- Page Configuration ---
st.set_page_config(page_title="BeeHayv", layout="wide", page_icon="🐝")

# --- Load User Authentication Config ---
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    
)

# --- Render Login Form FIRST ---
authenticator.login()

# --- THE LOGIN GATE ---
if st.session_state["authentication_status"]:
    # --- START OF LOGGED-IN APP ---
    st.sidebar.write(f'Welcome, *{st.session_state["name"]}*')
    authenticator.logout('Logout', 'sidebar')
    username = st.session_state["username"]

    # --- Initialize The Engine AFTER Login ---
    # This uses the Supabase connection string from secrets
    try:
        if 'tracker' not in st.session_state:
            conn_string = st.secrets["SUPABASE_CONNECTION_STRING"]
            st.session_state.tracker = BehaviorTracker(conn_string)
        tracker = st.session_state.tracker
    except Exception as e:
        st.error("Database connection failed. Please check your secrets configuration.")
        st.error(e)
        st.stop()
    
    # --- Main App UI ---
    st.title("🐝 BeeHayv Behavior Tracker")
    st.write("Welcome to your private behavior tracking dashboard.")
    st.divider()
    
    # ... (The rest of the UI forms and logic go here) ...
    st.header("1. Data Entry")
    # Fetch data for the current user
    user_subjects_df = tracker.get_subjects(username)
    user_defs_df = tracker.get_definitions(username)

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Add a New Subject"):
            with st.form("add_subject_form", clear_on_submit=True):
                new_subject_label = st.text_input("New Subject's Name or Label")
                submitted = st.form_submit_button("Add Subject")
                if submitted and new_subject_label:
                    tracker.add_subject(username, new_subject_label)
                    st.success(f"Added: '{new_subject_label}'")
                    st.rerun()

        with st.expander("➕ Define a New Behavior"):
            if user_subjects_df.empty:
                st.warning("Add a subject first.")
            else:
                with st.form("add_definition_form", clear_on_submit=True):
                    subject_options = pd.Series(user_subjects_df['subjectlabel'].values, index=user_subjects_df['subjectid'].values).to_dict()
                    selected_subject_id = st.selectbox("Select a Subject", options=list(subject_options.keys()), format_func=lambda x: subject_options.get(x))
                    new_behavior_name = st.text_input("New Behavior's Name")
                    submitted = st.form_submit_button("Define Behavior")
                    if submitted and selected_subject_id and new_behavior_name:
                        tracker.add_behavior_definition(username, selected_subject_id, new_behavior_name)
                        st.success(f"Defined '{new_behavior_name}'.")
                        st.rerun()
    with col2:
       # This is the corrected block for your app.py file

        with st.expander("📝 Log a Daily Score", expanded=True):
            user_defs_df = tracker.get_definitions(username)
            if user_defs_df.empty:
                st.warning("Define a behavior first.")
            else:
        # Create a user-friendly dictionary for display
                definition_options = pd.Series(
                    (user_defs_df['subjectlabel'] + " - " + user_defs_df['behaviorname']).values,
                    index=user_defs_df['definitionid'].values
                ).to_dict()

            with st.form("log_score_form", clear_on_submit=True):
            
                # --- START OF THE FIX ---
                # 1. Convert the option keys (the IDs) to strings for Streamlit
                options_as_strings = [str(k) for k in definition_options.keys()]

            # 2. Use the string list for options. The format_func will look up the display name.
            #    We convert x back to an int for the dictionary lookup.
            selected_definition_id_str = st.selectbox(
                "Select Behavior to Score",
                options=options_as_strings,
                format_func=lambda x: definition_options.get(int(x), "Invalid Behavior")
            )
            # --- END OF THE FIX ---

            score_date = st.date_input("Date of Observation", value=datetime.now())
            score_value = st.slider("Score (1-10)", 1, 10, 5)
            score_notes = st.text_area("Optional Notes")
            
            submitted = st.form_submit_button("Log Score")

            if submitted and selected_definition_id_str:
                # Convert the selected string ID back to an integer for the engine
                definition_id_to_log = int(selected_definition_id_str)
                tracker.log_score(username, definition_id_to_log, score_date, score_value, score_notes)
                st.success(f"Logged score of {score_value}.")
                st.rerun()