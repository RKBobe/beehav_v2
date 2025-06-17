# engine.py

import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

class BehaviorTracker:
    def __init__(self, db_connection_string):
        """
        Initializes the engine by connecting to the Supabase (PostgreSQL) database.
        """
        print("--- Instantiating Supabase-Driven BehaviorTracker Engine ---")
        try:
            # Create a SQLAlchemy engine. This object manages connections to the DB.
            self.engine = create_engine(db_connection_string)
            self._initialize_database()
            print("--- Engine is ready and connected to Supabase DB. ---")
        except Exception as e:
            print(f"🔥 DATABASE CONNECTION FAILED: {e}")
            raise e

    def _initialize_database(self):
        """Ensures all necessary tables exist in the database."""
        create_subjects_table = text("""
        CREATE TABLE IF NOT EXISTS subjects (
            SubjectID SERIAL PRIMARY KEY, username TEXT NOT NULL, SubjectLabel TEXT NOT NULL,
            DateCreated TIMESTAMPTZ DEFAULT NOW()
        );""")
        create_definitions_table = text("""
        CREATE TABLE IF NOT EXISTS definitions (
            DefinitionID SERIAL PRIMARY KEY, SubjectID INT REFERENCES subjects(SubjectID) ON DELETE CASCADE,
            username TEXT NOT NULL, BehaviorName TEXT NOT NULL, Description TEXT
        );""")
        create_scores_table = text("""
        CREATE TABLE IF NOT EXISTS daily_scores (
            LogID SERIAL PRIMARY KEY, DefinitionID INT REFERENCES definitions(DefinitionID) ON DELETE CASCADE,
            username TEXT NOT NULL, Date DATE NOT NULL, Score INT, Notes TEXT
        );""")
        with self.engine.connect() as connection:
            connection.execute(create_subjects_table)
            connection.execute(create_definitions_table)
            connection.execute(create_scores_table)
            connection.commit()
        print("Database tables verified.")

    # --- DATA READING METHODS ---
    def get_subjects(self, username):
        sql = text("SELECT * FROM subjects WHERE username = :user")
        with self.engine.connect() as connection:
            return pd.read_sql(sql, connection, params={"user": username})

    def get_definitions(self, username):
        # We join with subjects to get the subject label for display purposes
        sql = text("""
            SELECT d.*, s.SubjectLabel 
            FROM definitions d JOIN subjects s ON d.SubjectID = s.SubjectID
            WHERE d.username = :user
        """)
        with self.engine.connect() as connection:
            return pd.read_sql(sql, connection, params={"user": username})

    def get_daily_scores(self, username):
        sql = text("SELECT * FROM daily_scores WHERE username = :user")
        with self.engine.connect() as connection:
            return pd.read_sql(sql, connection, params={"user": username})

    # --- DATA WRITING METHODS ---
    def add_subject(self, username, subject_label):
        sql = text("INSERT INTO subjects (username, SubjectLabel, DateCreated) VALUES (:user, :label, :date)")
        params = {"user": username, "label": subject_label.strip(), "date": datetime.now()}
        with self.engine.connect() as connection:
            connection.execute(sql, params)
            connection.commit()

    def add_behavior_definition(self, username, subject_id, behavior_name, description=""):
        sql = text("INSERT INTO definitions (SubjectID, username, BehaviorName, Description) VALUES (:sid, :user, :bname, :desc)")
        params = {"sid": subject_id, "user": username, "bname": behavior_name.strip(), "desc": description.strip()}
        with self.engine.connect() as connection:
            connection.execute(sql, params)
            connection.commit()

    def log_score(self, username, definition_id, date, score, notes=""):
        sql = text("INSERT INTO daily_scores (DefinitionID, username, Date, Score, Notes) VALUES (:did, :user, :date, :score, :notes)")
        params = {"did": definition_id, "user": username, "date": date, "score": score, "notes": notes.strip()}
        with self.engine.connect() as connection:
            connection.execute(sql, params)
            connection.commit()