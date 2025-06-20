# api.py
import os
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime, date
import pandas as pd

# --- Load Environment Variables ---
load_dotenv()
DB_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING")

# --- Database Connection ---
try:
    if not DB_CONNECTION_STRING:
        raise ValueError("SUPABASE_CONNECTION_STRING not found in .env file or environment variables.")
    engine = create_engine(DB_CONNECTION_STRING)
except Exception as e:
    print(f"🔥 FAILED TO CREATE DATABASE ENGINE: {e}")
    engine = None

# --- Pydantic Models (Data Validation) ---
class SubjectCreate(BaseModel):
    subject_label: str

class SubjectUpdate(BaseModel):
    subject_label: str

class Subject(BaseModel):
    subjectid: int; username: str; subjectlabel: str; datecreated: datetime
    class Config: from_attributes = True

class DefinitionCreate(BaseModel):
    subject_id: int; behavior_name: str; description: str | None = None

class DefinitionUpdate(BaseModel):
    behavior_name: str
    description: str | None = None

class Definition(BaseModel):
    definitionid: int; subjectid: int; username: str; behaviorname: str; description: str | None; subjectlabel: str
    class Config: from_attributes = True

class ScoreCreate(BaseModel):
    definition_id: int; score_date: date; score: int; notes: str | None = None

class Score(BaseModel):
    logid: int; definitionid: int; username: str; date: date; score: int; notes: str | None
    class Config: from_attributes = True

class Averages(BaseModel):
    weekly: list[dict]
    monthly: list[dict]

class FeedbackCreate(BaseModel):
    feedback_text: str

# --- FastAPI App Instance ---
app = FastAPI()

# --- NEW: Database Initialization on Startup ---
@app.on_event("startup")
def on_startup():
    """Ensures all database tables exist when the API starts."""
    if engine is None:
        print("Skipping database initialization because engine failed to create.")
        return
        
    print("--- Verifying database tables on startup ---")
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
    create_feedback_table = text("""
    CREATE TABLE IF NOT EXISTS feedback (
        FeedbackID SERIAL PRIMARY KEY, username TEXT NOT NULL, submitted_at TIMESTAMPTZ DEFAULT NOW(),
        feedback_text TEXT
    );""")
    
    try:
        with engine.connect() as connection:
            connection.execute(create_subjects_table)
            connection.execute(create_definitions_table)
            connection.execute(create_scores_table)
            connection.execute(create_feedback_table)
            connection.commit()
        print("--- Database tables verified successfully ---")
    except Exception as e:
        print(f"🔥 DATABASE TABLE CREATION FAILED: {e}")


# --- "Dummy" Authentication ---
def get_current_user():
    return "RKBobe"

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the BeeHayv API!"}

@app.get("/health")
def health_check():
    if engine is None: raise HTTPException(status_code=500, detail="Database connection failed")
    return {"status": "ok", "database_connection": "successful"}

# --- Subjects Endpoints ---
@app.post("/subjects", response_model=Subject)
def add_subject(subject: SubjectCreate, current_user: str = Depends(get_current_user)):
    sql = text("INSERT INTO subjects (username, subjectlabel, datecreated) VALUES (:user, :label, :date) RETURNING *")
    params = {"user": current_user, "label": subject.subject_label.strip(), "date": datetime.now()}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params).mappings().first()
            connection.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/subjects", response_model=list[Subject])
def get_subjects(current_user: str = Depends(get_current_user)):
    sql = text("SELECT * FROM subjects WHERE username = :user ORDER BY subjectlabel")
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, {"user": current_user}).mappings().all()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/subjects/{subject_id}", response_model=Subject)
def update_subject(subject_id: int, subject: SubjectUpdate, current_user: str = Depends(get_current_user)):
    sql = text("UPDATE subjects SET subjectlabel = :label WHERE subjectid = :id AND username = :user RETURNING *")
    params = {"label": subject.subject_label, "id": subject_id, "user": current_user}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params).mappings().first()
            connection.commit()
        if result is None:
            raise HTTPException(status_code=404, detail="Subject not found or user does not have permission")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, current_user: str = Depends(get_current_user)):
    sql = text("DELETE FROM subjects WHERE subjectid = :id AND username = :user")
    params = {"id": subject_id, "user": current_user}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params)
            if result.rowcount == 0:
                 raise HTTPException(status_code=404, detail="Subject not found or user does not have permission")
            connection.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Definitions Endpoints ---
def _get_single_definition(connection, username: str, definition_id: int):
    sql = text("SELECT d.*, s.subjectlabel FROM definitions d JOIN subjects s ON d.subjectid = s.subjectid WHERE d.username = :user AND d.definitionid = :did")
    return connection.execute(sql, {"user": username, "did": definition_id}).mappings().first()

@app.post("/definitions", response_model=Definition)
def add_definition(definition: DefinitionCreate, current_user: str = Depends(get_current_user)):
    sql = text("INSERT INTO definitions (subjectid, username, behaviorname, description) VALUES (:sid, :user, :bname, :desc) RETURNING *")
    params = {"sid": definition.subject_id, "user": current_user, "bname": definition.behavior_name.strip(), "desc": definition.description}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params).mappings().first()
            connection.commit()
            if result:
                return _get_single_definition(connection, current_user, result['definitionid'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/definitions", response_model=list[Definition])
def get_definitions(current_user: str = Depends(get_current_user)):
    sql = text("SELECT d.*, s.subjectlabel FROM definitions d JOIN subjects s ON d.subjectid = s.subjectid WHERE d.username = :user ORDER BY s.subjectlabel, d.behaviorname")
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, {"user": current_user}).mappings().all()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/definitions/{definition_id}", response_model=Definition)
def update_definition(definition_id: int, definition: DefinitionUpdate, current_user: str = Depends(get_current_user)):
    sql = text("UPDATE definitions SET behaviorname = :bname, description = :desc WHERE definitionid = :id AND username = :user")
    params = {"bname": definition.behavior_name, "desc": definition.description, "id": definition_id, "user": current_user}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Definition not found or user does not have permission")
            connection.commit()
            return _get_single_definition(connection, current_user, definition_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/definitions/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_definition(definition_id: int, current_user: str = Depends(get_current_user)):
    sql = text("DELETE FROM definitions WHERE definitionid = :id AND username = :user")
    params = {"id": definition_id, "user": current_user}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Definition not found or user does not have permission")
            connection.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Scores Endpoints ---
@app.post("/scores", response_model=Score)
def add_score(score: ScoreCreate, current_user: str = Depends(get_current_user)):
    sql = text("INSERT INTO daily_scores (definitionid, username, date, score, notes) VALUES (:did, :user, :date, :score, :notes) RETURNING *")
    params = {"did": score.definition_id, "user": current_user, "date": score.score_date, "score": score.score, "notes": score.notes}
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, params).mappings().first()
            connection.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scores", response_model=list[Score])
def get_scores(current_user: str = Depends(get_current_user)):
    sql = text("SELECT * FROM daily_scores WHERE username = :user ORDER BY date DESC")
    try:
        with engine.connect() as connection:
            result = connection.execute(sql, {"user": current_user}).mappings().all()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Averages Endpoint ---
@app.get("/averages", response_model=Averages)
def get_averages(current_user: str = Depends(get_current_user)):
    sql = text("SELECT * FROM daily_scores WHERE username = :user")
    try:
        with engine.connect() as connection:
            scores_df = pd.read_sql(sql, connection, params={"user": current_user})
        
        if scores_df.empty: return {"weekly": [], "monthly": []}

        scores_df['date'] = pd.to_datetime(scores_df['date'], errors='coerce')
        scores_df.dropna(subset=['date'], inplace=True)
        scores_df['score'] = pd.to_numeric(scores_df['score'], errors='coerce')
        scores_df.dropna(subset=['score'], inplace=True)
        
        if scores_df.empty: return {"weekly": [], "monthly": []}
        
        scores_df['score'] = scores_df['score'].astype(int)
        scores_df['year'] = scores_df['date'].dt.isocalendar().year
        
        scores_df['weekofyear'] = scores_df['date'].dt.isocalendar().week
        weekly_avg = scores_df.groupby(['definitionid', 'year', 'weekofyear'])['score'].agg(['mean', 'count']).reset_index()
        weekly_avg.rename(columns={'mean': 'averagescore', 'count': 'datapointscount'}, inplace=True)
        
        scores_df['month'] = scores_df['date'].dt.month
        monthly_avg = scores_df.groupby(['definitionid', 'year', 'month'])['score'].agg(['mean', 'count']).reset_index()
        monthly_avg.rename(columns={'mean': 'averagescore', 'count': 'datapointscount'}, inplace=True)

        return {"weekly": weekly_avg.to_dict('records'), "monthly": monthly_avg.to_dict('records')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Feedback Endpoint ---
@app.post("/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(feedback: FeedbackCreate, current_user: str = Depends(get_current_user)):
    sql = text("INSERT INTO feedback (username, feedback_text) VALUES (:user, :text)")
    params = {"user": current_user, "text": feedback.feedback_text}
    try:
        with engine.connect() as connection:
            connection.execute(sql, params)
            connection.commit()
        return {"status": "success", "message": "Thank you for your feedback!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
