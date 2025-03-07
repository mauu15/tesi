import datetime, math
import os, sys
import pandas as pd
from operators_requests import Operator, Request, Node
from typing import List, Optional, Tuple

scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_path)

# script che implementa le 4 varianti dell'algoritmo GRS
# 1. GRS - Time: minimizza gli spostamenti tau
# 2. GRS - Saturami: minimizza ho, il tempo rimanente prima della fine della sessione di un operatore
# 3. GRS - LasciamiInPace: massimizza ho, il tempo rimanente prima della fine della sessione di un operatore
# 4. GRS - TradeOff: minimizza wo (la quantità di tempo che ha lavorato un operatore) + tau (gli spostamenti) + ti (durata della richiesta)

# Importo gli operatori, le richieste e i pazienti dai file csv
from data_loader import operators, requests, patients

import json

# Carica la matrice delle distanze dal file JSON
base_dir = os.path.join(os.path.dirname(__file__), '..', 'mapping')
json_path = os.path.join(base_dir, "distance_matrix_pane_rose.json")

import ast

with open(json_path, "r", encoding="utf-8") as f:
    content = f.read()
    distance_matrix = ast.literal_eval(content)


def get_distance(id1, id2):
    a, b = int(id1), int(id2)
    key = (min(a, b), max(a, b))
    return distance_matrix.get(key, float("inf"))


def grs(variant, operators, requests, patients):
    """
    Funzione unica per l'algoritmo GRS che, in base alla variante scelta,
    assegna le richieste agli operatori.

    :param variant: Nome della variante dell'algoritmo GRS.
    :param operators: Lista di operatori.
    :param requests: Lista di richieste.
    :param patients: Lista di pazienti.
    """

    assignments = {}

    for op in operators:
        if "eo" not in op:
            op["eo"] = 420            # Inizio turno (es. 420 minuti = 7:00 AM)
        if "ho" not in op:
            op["ho"] = 300            # Tempo residuo della sessione (300 minuti)
        if "wo" not in op:
            op["wo"] = 0              # Tempo già lavorato, inizialmente 0
        if "Lo" not in op:
            op["Lo"] = []             # Lista delle richieste assegnate
        if "current_patient" not in op:
            op["current_patient"] = {"id": op["id"], "lat": op["lat"], "lon": op["lon"]}

    # Ordina le richieste per il tempo minimo di inizio (α_i)
    sorted_requests = sorted(requests, key=lambda r: r["min_time_begin"])

    # Ciclo greedy: per ogni richiesta, seleziona l'operatore migliore in base al costo
    for req in sorted_requests:
        best_op = None
        best_cost = float("inf")

        for op in operators:
            # Calcola il tempo di spostamento dalla posizione corrente dell'operatore al paziente della richiesta
            travel_time = compute_travel_time(op, req, patients)
            start_time = op["eo"] + travel_time
            finish_time = start_time + req["duration"]

            # Verifica se l'operatore può completare la richiesta entro il tempo disponibile
            if finish_time <= op["eo"] + op["ho"]:
                cost = compute_cost(variant, op, req, travel_time)
                if cost < best_cost:
                    best_cost = cost
                    best_op = op

        # Se troviamo un operatore adatto, assegniamo la richiesta e aggiorniamo le variabili
        if best_op is not None:
            travel_time = compute_travel_time(best_op, req, patients)
            best_op["eo"] += travel_time + req["duration"]    # e_o = e_o + τ + t_i
            best_op["wo"] += req["duration"]                  # w_o = w_o + t_i
            best_op["ho"] -= req["duration"]                  # h_o = h_o - t_i

            # Aggiorna la posizione corrente dell'operatore cercando il paziente corrispondente
            patient = next((p for p in patients if p["id"] == req["project_id"]), None)
            if patient is not None:
                best_op["current_patient"] = patient

            best_op["Lo"].append(req["id"])                   # aggiunge la richiesta alla lista
            assignments.setdefault(best_op["id"], []).append(req["id"])


    return assignments


def is_operator_available(op, req):
    return True


def compute_travel_time(op, req, patients):
    """
    Calcola il tempo di spostamento (tau) utilizzando la matrice delle distanze.
    Si usano gli id globali: l'id dell'operatore e l'id del paziente.
    """
    patient = next((p for p in patients if p["id"] == req["project_id"]), None)
    if patient is None:
        return float("inf")
    return get_distance(op["id"], patient["id"])



def compute_cost(variant, op, req, travel_time):
    """
    Calcola il "costo" di assegnare la richiesta a un operatore, 
    in base alla variante scelta.
    """
    if variant == "Time":
        # Minimizza il tempo di spostamento (travel_time)
        return travel_time

    elif variant == "Saturami":
        # Minimizza ho dopo l'assegnazione => ho_final = op["ho"] - req["duration"]
        # min cost => cost = -ho_final
        ho_final = op["ho"] - req["duration"]
        return -ho_final

    elif variant == "LasciamiInPace":
        # Massimizza ho => cost = ho_final (oppure -ho_final invertendo la logica)
        ho_final = op["ho"] - req["duration"]
        return ho_final

    elif variant == "TradeOff":
        # Minimizza (wo + travel_time + ti)
        wo = op["wo"]
        ti = req["duration"]
        return wo + travel_time + ti

    else:
        raise ValueError(f"Variante {variant} non valida")


def update_operator(op, req, patients):
    """
    Aggiorna lo stato dell'operatore dopo aver assegnato una richiesta:
      - Diminuisce il tempo disponibile (max_weekly_hours) in base alla durata della richiesta.
      - Aggiorna la posizione dell'operatore alla posizione del paziente.
    """
    op["max_weekly_hours"] -= req["duration"]
    patient = next((p for p in patients if p["id"] == req["project_id"]), None)
    if patient:
        op["lat"] = patient["lat"]
        op["lon"] = patient["lon"]

def display_assignments(assignments):
    data = []
    for op_id, req_list in assignments.items():
        data.append({
            "Operator ID": op_id,
            "Num Requests": len(req_list),
            "Request IDs": ", ".join(req_list)
        })
    df = pd.DataFrame(data)
    return df

variants = ["Time", "Saturami", "LasciamiInPace", "TradeOff"]

for variant in variants:
    # print(f"\n--- Variante: {variant} ---")
    assignments = grs(variant, operators, requests, patients)
    df_assignments = display_assignments(assignments)
    # print(df_assignments)
    # Salva il DataFrame in un file CSV con il nome che include la variante
    
    results_dir = os.path.join(os.path.dirname(__file__), '..', 'variants_results')
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    df_assignments.to_csv(os.path.join(results_dir, f"assignments_{variant}.csv"), index=False)
    print(f"File 'assignments_{variant}.csv' salvato con successo.")
