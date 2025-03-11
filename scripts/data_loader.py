import csv
import os

def read_operators(file_path):
    """
    Legge il file operators.csv e restituisce una lista di dizionari
    con i campi utili per GRS:
      - id
      - max_weekly_hours
      - available_days
      - lat
      - lon
    """
    operators = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = {
                "id": row["id"],
                "name": row["name"],
                "surname": row["surname"],
                "weekly_worked": 0, #wo, in minutes
                "max_weekly_minutes": int(float(row["max_weekly_hours"]) * 60) if row["max_weekly_hours"] else 0, # H_o
                "lat": float(row["lat"]) if row["lat"] else 0.0,
                "lon": float(row["lon"]) if row["lon"] else 0.0,
                "hourly_rate": float(row["hourly_rate"]) if row["hourly_rate"] else 0.0,
                "current_patient_id": None,
            }
            operators.append(op)
    return operators

def read_requests(file_path):
    """
    Legge il file requests.csv e restituisce una lista di dizionari
    con i campi utili per GRS:
      - id
      - project_id (id del paziente)
      - day
      - n_operators_required
      - duration
      - min_time_begin
      - max_time_begin
    """
    requests = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            req = {
                "id": row["id"],
                "project_id": row["project_id"],
                "day": int(row["day"]) if row["day"] else None,
                "n_operators_required": int(row["n_operators_required"]) if row["n_operators_required"] else float("inf"),
                "duration": int(float(row["duration"])) if row["duration"] else 0,
                "min_time_begin": int(float(row["min_time_begin"])) if row["min_time_begin"] else 0,
                "max_time_begin": int(float(row["max_time_begin"])) if row["max_time_begin"] else 0
            }
            requests.append(req)
    return requests

def read_patients(file_path):
    """
    Legge il file patients.csv e restituisce una lista di dizionari
    con i campi utili per GRS:
      - id
      - lat
      - lon
    """
    patients = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = {
                "id": row["id"],
                "lat": float(row["lat"]) if row["lat"] else 0.0,
                "lon": float(row["lon"]) if row["lon"] else 0.0
            }
            patients.append(p)
    return patients


base_dir = os.path.join(os.path.dirname(__file__), '..', 'csv')
OPERATORS_FILE = os.path.join(base_dir, "operators.csv")
REQUESTS_FILE = os.path.join(base_dir, "requests.csv")
PATIENTS_FILE = os.path.join(base_dir, "patients.csv")


operators = read_operators(OPERATORS_FILE)
requests = read_requests(REQUESTS_FILE)
patients = read_patients(PATIENTS_FILE)
