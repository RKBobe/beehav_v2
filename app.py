# app.py

import streamlit as st
import pandas as pd
from engine import BehaviorTracker
from datetime import datetime
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import requests 
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
    st.error("Authentication configuration file (`config.yaml`) not found. Please ensure it exists in your repository.")
    st.stop()

# --- Render Login Form FIRST ---
col1_login, col2_login, col3_login = st.columns([1,2,1])
with col2_login:
    authenticator.login()

# --- THE LOGIN GATE ---
if st.session_state["authentication_status"]:
    # --- START OF LOGGED-IN APP ---
    st.sidebar.write(f'Welcome, *{st.session_state["name"]}*')
    authenticator.logout('Logout', 'sidebar')
    username = st.session_state["username"]

    # --- Initialize The Engine to be an API Client ---
    API_URL = "http://127.0.0.1:8000" 
    try:
        if 'tracker' not in st.session_state:
            st.session_state.tracker = BehaviorTracker(base_api_url=API_URL)
        tracker = st.session_state.tracker
        health_check = requests.get(f"{API_URL}/health")
        if health_check.status_code != 200:
            st.error("API backend not responding. Please ensure it is running.")
            st.stop()
    except requests.exceptions.ConnectionError:
        st.error("API connection failed. Is the API server running?")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.stop()
    
    # --- Main App UI ---
    st.title("🐝 BeeHayv Behavior Tracker")
    st.write("This app is now powered by the FastAPI backend.")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Entry & Plotting", "⚙️ Data Management", "📚 Raw Data Tables", "📝 Submit Feedback"])

    # --- Fetch data once for all tabs ---
    user_subjects_df = tracker.get_subjects(username)
    user_defs_df = tracker.get_definitions(username)

    with tab1: # Data Entry & Plotting
        st.header("1. Data Entry")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            with st.expander("➕ Add a New Subject"):
                with st.form("add_subject_form", clear_on_submit=True):
                    new_subject_label = st.text_input("New Subject's Name")
                    submitted = st.form_submit_button("Add Subject")
                    if submitted and new_subject_label:
                        tracker.add_subject(username, new_subject_label)
                        st.success(f"Added: '{new_subject_label}'"); st.rerun()
            with st.expander("➕ Define a New Behavior"):
                if user_subjects_df.empty:
                    st.warning("Add a subject first.")
                else:
                    with st.form("add_definition_form", clear_on_submit=True):
                        subject_options = pd.Series(user_subjects_df['subjectlabel'].values, index=user_subjects_df['subjectid'].values).to_dict()
                        selected_subject_id = st.selectbox("For Subject", options=list(subject_options.keys()), format_func=lambda x: subject_options.get(x))
                        new_behavior_name = st.text_input("New Behavior's Name")
                        submitted = st.form_submit_button("Define Behavior")
                        if submitted and selected_subject_id and new_behavior_name:
                            tracker.add_behavior_definition(username, selected_subject_id, new_behavior_name)
                            st.success(f"Defined '{new_behavior_name}'."); st.rerun()
        with d_col2:
            with st.expander("📝 Log a Daily Score", expanded=True):
                if user_defs_df.empty:
                    st.warning("Define a behavior first.")
                else:
                    user_defs_df['display_label'] = user_defs_df['subjectlabel'].fillna('') + " - " + user_defs_df['behaviorname'].fillna('')
                    definition_options = pd.Series(user_defs_df['display_label'].values, index=user_defs_df['definitionid'].values).to_dict()
                    with st.form("log_score_form", clear_on_submit=True):
                        options_as_strings = [str(k) for k in definition_options.keys()]
                        selected_definition_id_str = st.selectbox("Select Behavior", options=options_as_strings, format_func=lambda x: definition_options.get(int(x), "Select..."))
                        score_date = st.date_input("Date", value=datetime.now())
                        score_value = st.slider("Score (1-10)", 1, 10, 5)
                        score_notes = st.text_area("Notes (Optional)")
                        submitted = st.form_submit_button("Log Score")
                        if submitted and selected_definition_id_str:
                            tracker.log_score(username, int(selected_definition_id_str), score_date, score_value, score_notes)
                            st.success(f"Logged score of {score_value}."); st.rerun()
        st.divider()
        st.header("2. Analysis & Plotting")
        if st.button("📈 Calculate Averages", type="primary"):
            with st.spinner("Calculating..."):
                weekly_df, monthly_df = tracker.get_all_averages(username)
                st.session_state.weekly_df = weekly_df
                st.session_state.monthly_df = monthly_df
                st.success("Averages calculated!")
        if 'weekly_df' in st.session_state:
            st.subheader("Progress Charts")
            if user_defs_df.empty:
                st.warning("No behaviors defined to plot.")
            else:
                plot_col1, plot_col2 = st.columns([1, 2])
                with plot_col1:
                    user_defs_df['plot_display_label'] = user_defs_df['subjectlabel'].fillna('') + " - " + user_defs_df['behaviorname'].fillna('')
                    plot_definition_options = pd.Series(user_defs_df['plot_display_label'].values, index=user_defs_df['definitionid'].values).to_dict()
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
                        else:
                            avg_df = st.session_state.monthly_df
                            if not avg_df.empty:
                                avg_df['Time Period'] = pd.to_datetime(avg_df[['year', 'month']].assign(DAY=1)).dt.strftime('%Y-%b')
                            x_axis, y_axis = 'Time Period', 'averagescore'
                        if 'Time Period' in avg_df:
                            plot_data = avg_df[avg_df['definitionid'] == behavior_to_plot].sort_values(by='Time Period')
                            if not plot_data.empty:
                                fig = px.line(plot_data, x=x_axis, y=y_axis, title=f"{period_to_plot} Progress for {plot_definition_options.get(behavior_to_plot, 'N/A')}", markers=True, labels={x_axis: "Time Period", y_axis: "Average Score"})
                                fig.update_yaxes(range=[0, 11]); st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No calculated averages to plot for this specific behavior yet.")

    with tab2: # Data Management
        st.header("Manage Your Data")
        manage_col1, manage_col2 = st.columns(2)
        with manage_col1:
            st.subheader("Edit Data")
            with st.expander("✏️ Update Subject Name"):
                if not user_subjects_df.empty:
                    with st.form("update_subject_form"):
                        subject_options = pd.Series(user_subjects_df['subjectlabel'].values, index=user_subjects_df['subjectid'].values).to_dict()
                        subject_options_keys_str = [str(k) for k in subject_options.keys()]
                        subject_to_edit_str = st.selectbox("Subject to Update", options=subject_options_keys_str, format_func=lambda x: subject_options.get(int(x)))
                        new_subject_label = st.text_input("New Name")
                        submitted_update = st.form_submit_button("Update Subject")
                        if submitted_update and subject_to_edit_str and new_subject_label:
                            tracker.update_subject(username, int(subject_to_edit_str), new_subject_label)
                            st.success(f"Updated subject."); st.rerun()
                else:
                    st.warning("No subjects to edit.")
            with st.expander("✏️ Update Behavior Definition"):
                 if not user_defs_df.empty:
                    with st.form("update_definition_form"):
                        user_defs_df['mng_display_label'] = user_defs_df['subjectlabel'].fillna('') + " - " + user_defs_df['behaviorname'].fillna('')
                        def_options = pd.Series(user_defs_df['mng_display_label'].values, index=user_defs_df['definitionid'].values).to_dict()
                        def_options_keys_str = [str(k) for k in def_options.keys()]
                        def_to_edit_str = st.selectbox("Definition to Update", options=def_options_keys_str, format_func=lambda x: def_options.get(int(x)))
                        current_name, current_desc = "", ""
                        if def_to_edit_str:
                            def_to_edit = int(def_to_edit_str)
                            current_name = user_defs_df.loc[user_defs_df['definitionid'] == def_to_edit, 'behaviorname'].iloc[0] if not user_defs_df.loc[user_defs_df['definitionid'] == def_to_edit].empty else ""
                            current_desc = user_defs_df.loc[user_defs_df['definitionid'] == def_to_edit, 'description'].iloc[0] if not user_defs_df.loc[user_defs_df['definitionid'] == def_to_edit].empty else ""
                        new_def_name = st.text_input("New Behavior Name", value=current_name)
                        new_def_desc = st.text_area("New Description", value=current_desc)
                        submitted_def_update = st.form_submit_button("Update Definition")
                        if submitted_def_update and def_to_edit_str:
                            tracker.update_definition(username, int(def_to_edit_str), new_def_name, new_def_desc)
                            st.success("Updated definition."); st.rerun()
                 else:
                    st.warning("No definitions to edit.")
        with manage_col2:
            st.subheader("Delete Data")
            with st.expander("🗑️ Delete Subject"):
                if not user_subjects_df.empty:
                    with st.form("delete_subject_form"):
                        subject_options_del = pd.Series(user_subjects_df['subjectlabel'].values, index=user_subjects_df['subjectid'].values).to_dict()
                        subject_del_keys_str = [str(k) for k in subject_options_del.keys()]
                        subject_to_delete_str = st.selectbox("Subject to Delete", options=subject_del_keys_str, format_func=lambda x: subject_options_del.get(int(x)))
                        confirmation = st.checkbox("I am sure. This deletes the subject and ALL its data.")
                        submitted_del = st.form_submit_button("Delete Subject Permanently")
                        if submitted_del and subject_to_delete_str and confirmation:
                            tracker.delete_subject(username, int(subject_to_delete_str))
                            st.success(f"Deleted subject."); st.rerun()
            with st.expander("🗑️ Delete Behavior Definition"):
                if not user_defs_df.empty:
                    with st.form("delete_definition_form"):
                        user_defs_df['del_display_label'] = user_defs_df['subjectlabel'].fillna('') + " - " + user_defs_df['behaviorname'].fillna('')
                        def_options_del = pd.Series(user_defs_df['del_display_label'].values, index=user_defs_df['definitionid'].values).to_dict()
                        def_del_keys_str = [str(k) for k in def_options_del.keys()]
                        def_to_delete_str = st.selectbox("Definition to Delete", options=def_del_keys_str, format_func=lambda x: def_options_del.get(int(x)))
                        conf_del_def = st.checkbox("I am sure. This deletes the definition and its scores.")
                        submitted_del_def = st.form_submit_button("Delete Definition Permanently")
                        if submitted_del_def and def_to_delete_str and conf_del_def:
                            tracker.delete_definition(username, int(def_to_delete_str))
                            st.success("Deleted definition."); st.rerun()
    with tab3:
        st.header("Raw Data Views")
        st.subheader("Subjects Table")
        st.dataframe(user_subjects_df)
        st.subheader("Definitions Table")
        st.dataframe(user_defs_df)
        st.subheader("Daily Scores Log")
        st.dataframe(tracker.get_daily_scores(username))
    
    with tab4:
        st.header("Submit Feedback")
        st.write("Find a bug or have a suggestion? Let us know!")
        with st.form("feedback_form", clear_on_submit=True):
            feedback_text = st.text_area("Your feedback:", height=150)
            submitted_feedback = st.form_submit_button("Submit Feedback")
            if submitted_feedback and feedback_text:
                tracker.submit_feedback(username, feedback_text)
                st.success("Thank you! Your feedback has been submitted.")


elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')

elif st.session_state["authentication_status"] is None:
    st.warning('Please login to continue.')
    st.subheader("Don't have an account?")
    try:
        if authenticator.register_user(
            fields={'Form name': 'New User Registration', 'Username': 'Username', 'Name': 'Full Name', 'Email': 'Email', 'Password': 'Password', 'Repeat Password': 'Confirm Password'},
            location='main',
        ):
            with open('config.yaml', 'w') as file:
                yaml.dump(config, file, default_flow_style=False)
            st.success('User registered successfully! Please login above.')
    except Exception as e:
        st.error(e)
