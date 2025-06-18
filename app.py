# app.py - FINAL HARDENED VERSION

import streamlit as st
import pandas as pd
from engine import BehaviorTracker
from datetime import datetime
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(page_title="BeeHayv", layout="wide", page_icon="🐝")

# --- Load User Authentication Config ---
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

except FileNotFoundError:
    st.error("Authentication configuration file (`config.yaml`) not found. Please ensure it is in your repository.")
    st.stop()


# --- Render Login Form FIRST ---
authenticator.login()

# --- THE LOGIN GATE ---
if st.session_state["authentication_status"]:
    # --- START OF LOGGED-IN APP ---
    st.sidebar.write(f'Welcome, *{st.session_state["name"]}*')
    authenticator.logout('Logout', 'sidebar')
    username = st.session_state["username"]

    # --- Initialize The Engine AFTER Login ---
    try:
        # This uses the Supabase connection string from secrets
        if 'tracker' not in st.session_state:
            conn_string = st.secrets["SUPABASE_CONNECTION_STRING"]
            st.session_state.tracker = BehaviorTracker(conn_string)
        tracker = st.session_state.tracker
    except Exception as e:
        st.error("Database connection failed. Please check your secrets configuration on Streamlit Cloud.")
        st.error(f"Details: {e}")
        st.stop()
    
    # --- Main App UI ---
    st.title("🐝 BeeHayv Behavior Tracker")
    st.write("Welcome to your private behavior tracking dashboard.")
    st.divider()
    
    st.header("1. Data Entry")
    # Fetch data for the current user once at the top
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
        with st.expander("📝 Log a Daily Score", expanded=True):
            if user_defs_df.empty:
                st.warning("Define a behavior first.")
            else:
                # Sanitize data to prevent TypeErrors from missing values
                safe_subject_labels = user_defs_df['subjectlabel'].fillna('')
                safe_behavior_names = user_defs_df['behaviorname'].fillna('')
                user_defs_df['display_label'] = safe_subject_labels + " - " + safe_behavior_names
                
                definition_options = pd.Series(user_defs_df['display_label'].values, index=user_defs_df['definitionid'].values).to_dict()
                
                with st.form("log_score_form", clear_on_submit=True):
                    options_as_strings = [str(k) for k in definition_options.keys()]
                    selected_definition_id_str = st.selectbox("Select Behavior to Score", options=options_as_strings, format_func=lambda x: definition_options.get(int(x), "Invalid Behavior"))
                    score_date = st.date_input("Date of Observation", value=datetime.now())
                    score_value = st.slider("Score (1-10)", 1, 10, 5)
                    score_notes = st.text_area("Optional Notes")
                    submitted = st.form_submit_button("Log Score")

                    if submitted and selected_definition_id_str:
                        definition_id_to_log = int(selected_definition_id_str)
                        tracker.log_score(username, definition_id_to_log, score_date, score_value, score_notes)
                        st.success(f"Logged score of {score_value}.")
                        st.rerun()
    
    st.divider()

    st.header("2. Analysis & Plotting")

    if st.button("📈 Calculate Averages", type="primary", help="Recalculate all averages based on the current score log."):
        with st.spinner("Calculating..."):
            weekly_df, monthly_df, _ = tracker.calculate_all_averages(username)
            st.session_state.weekly_df = weekly_df
            st.session_state.monthly_df = monthly_df
            st.success("Averages have been calculated!")

    if 'weekly_df' in st.session_state and not st.session_state.weekly_df.empty:
        st.subheader("Progress Charts")
        if user_defs_df.empty:
            st.warning("No behaviors defined to plot.")
        else:
            plot_col1, plot_col2 = st.columns([1, 2])
            with plot_col1:
                # Sanitize data for the plotting dropdown as well
                safe_plot_subject_labels = user_defs_df['subjectlabel'].fillna('')
                safe_plot_behavior_names = user_defs_df['behaviorname'].fillna('')
                plot_display_labels = safe_plot_subject_labels + " - " + safe_plot_behavior_names
                
                plot_definition_options = pd.Series(plot_display_labels.values, index=user_defs_df['definitionid'].values).to_dict()
                
                behavior_to_plot_str = st.selectbox("Select Behavior to Plot", options=[str(k) for k in plot_definition_options.keys()], format_func=lambda x: plot_definition_options.get(int(x)))
                period_to_plot = st.radio("Select Period", ["Weekly", "Monthly"], horizontal=True)

            with plot_col2:
                if 'behavior_to_plot_str' in locals() and behavior_to_plot_str:
                    behavior_to_plot = int(behavior_to_plot_str)
                    
                    if period_to_plot == "Weekly":
                        avg_df = st.session_state.weekly_df
                        if not avg_df.empty:
                            avg_df['Time Period'] = avg_df['year'].astype(str) + "-W" + avg_df['weekofyear'].astype(str).str.zfill(2)
                        x_axis, y_axis = 'Time Period', 'averagescore'
                    else: # Monthly
                        avg_df = st.session_state.monthly_df
                        if not avg_df.empty:
                            avg_df['Time Period'] = pd.to_datetime(avg_df[['year', 'month']].assign(DAY=1)).dt.strftime('%Y-%b')
                        x_axis, y_axis = 'Time Period', 'averagescore'

                    if not avg_df.empty:
                        plot_data = avg_df[avg_df['definitionid'] == behavior_to_plot].sort_values(by='Time Period')
                        if not plot_data.empty:
                            fig = px.line(plot_data, x=x_axis, y=y_axis, title=f"{period_to_plot} Progress for {plot_definition_options.get(behavior_to_plot, 'N/A')}", markers=True, labels={x_axis: "Time Period", y_axis: "Average Score"})
                            fig.update_yaxes(range=[0, 11])
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No calculated averages to plot for this specific behavior yet.")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please login. Contact an administrator to create an account.')
