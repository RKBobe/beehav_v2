# engine.py

import requests
import pandas as pd
from datetime import date

class BehaviorTracker:
    def __init__(self, base_api_url: str):
        """
        Initializes the engine with the base URL of the FastAPI server.
        """
        self.base_url = base_api_url
        self.headers = {"accept": "application/json"}

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """A helper method to make requests and handle errors."""
        try:
            response = requests.request(method, f"{self.base_url}{endpoint}", headers=self.headers, **kwargs)
            response.raise_for_status() # Raises an error for bad status codes (4xx or 5xx)
            if response.status_code == 204: # No Content success status (for DELETE)
                return None
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} - {response.text}")
            raise
        except Exception as err:
            print(f"Other error occurred: {err}")
            raise

    # --- DATA READING METHODS ---
    def get_subjects(self, username: str) -> pd.DataFrame:
        data = self._make_request("get", "/subjects")
        return pd.DataFrame(data)

    def get_definitions(self, username: str) -> pd.DataFrame:
        data = self._make_request("get", "/definitions")
        return pd.DataFrame(data)

    def get_daily_scores(self, username: str) -> pd.DataFrame:
        data = self._make_request("get", "/scores")
        return pd.DataFrame(data)
        
    def get_all_averages(self, username: str):
        data = self._make_request("get", "/averages")
        weekly_df = pd.DataFrame(data.get('weekly', []))
        monthly_df = pd.DataFrame(data.get('monthly', []))
        return weekly_df, monthly_df

    # --- DATA WRITING METHODS ---
    def add_subject(self, username: str, subject_label: str):
        return self._make_request("post", "/subjects", json={"subject_label": subject_label})

    def add_behavior_definition(self, username: str, subject_id: int, behavior_name: str, description: str = ""):
        payload = {"subject_id": subject_id, "behavior_name": behavior_name, "description": description}
        return self._make_request("post", "/definitions", json=payload)

    def log_score(self, username: str, definition_id: int, score_date: date, score: int, notes: str = ""):
        payload = {"definition_id": definition_id, "score_date": score_date.isoformat(), "score": score, "notes": notes}
        return self._make_request("post", "/scores", json=payload)
        
    # --- EDITING METHODS ---
    def update_subject(self, username: str, subject_id: int, new_label: str):
        return self._make_request("put", f"/subjects/{subject_id}", json={"subject_label": new_label})

    def update_definition(self, username: str, definition_id: int, new_name: str, new_description: str):
        payload = {"behavior_name": new_name, "description": new_description}
        return self._make_request("put", f"/definitions/{definition_id}", json=payload)

    # --- DELETING METHODS ---
    def delete_subject(self, username: str, subject_id: int):
        return self._make_request("delete", f"/subjects/{subject_id}")
        
    def delete_definition(self, username: str, definition_id: int):
        return self._make_request("delete", f"/definitions/{definition_id}")
