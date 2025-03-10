import datetime, math
import os, sys
import pandas as pd
from operators_requests import Operator, Request, Node
from typing import List, Optional, Tuple

scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_path)

# script che implementa le 4 varianti dell'algoritmo GRS
# 1. GRS - Time: minimizza gli spostamenti tau
# 2. GRS - Saturami: minimizza ho, il tempo rimanente prima della fine della sessione di un operatore
# 3. GRS - LasciamiInPace: massimizza ho, il tempo rimanente prima della fine della sessione di un operatore
# 4. GRS - TradeOff: minimizza wo (la quantità di tempo che ha lavorato un operatore) + tau (gli spostamenti) + ti (durata della richiesta)

# Importo gli operatori, le richieste e i pazienti dai file csv
from data_loader import operators, requests, patients

import json
from data_loader import operators, requests, patients  # I dati vengono importati dal modulo data_loader

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


def set_operator_state_afternoon(operator):
    """
    Reimposta lo stato dell'operatore per il turno pomeridiano.
    Se l'operatore ha lavorato al mattino (flag "worked_morning" == True),
    il turno pomeridiano inizia alle 18:00 (1080 minuti), altrimenti alle 16:00 (960 minuti).
    """
    if operator.get("worked_morning", True):
        operator["eo_start_afternoon"] = 1080
        operator["eo"] = 1080
    else:
        operator["eo_start_afternoon"] = 960
        operator["eo"] = 960

    operator["ho"] = 300
    operator["wo"] = 0
    operator["Lo"] = []

def set_operator_state_morning(operator):
    """
    Reimposta lo stato dell'operatore per il turno mattutino.
    Il turno mattutino inizia alle 7:00 (420 minuti).
    """
    operator["eo"] = 420
    operator["ho"] = 300
    operator["wo"] = 0
    operator["Lo"] = []

def grs(variant, operators, requests, patients, shift_end=720):
    """
    Funzione unica per l'algoritmo GRS che, in base alla variante scelta,
    assegna le richieste agli operatori.

    :param variant: Nome della variante dell'algoritmo GRS.
    :param operators: Lista di operatori (dizionari).
    :param requests: Lista di richieste (dizionari).
    :param patients: Lista di pazienti (dizionari).
    """

    assignments = {}

    # Inizializza i campi mancanti per ogni operatore
    for op in operators:
        if "eo" not in op:
            op["eo"] = 420         # Inizio turno (420 minuti = 7:00 AM)
        if "ho" not in op:
            op["ho"] = 300      # Tempo residuo della sessione (300 minuti)
        if "wo" not in op:
            op["wo"] = 0           # Tempo già lavorato, inizialmente 0
        if "Lo" not in op:
            op["Lo"] = []          # Lista delle richieste assegnate
        
    

    # Ordina le richieste per il tempo minimo di inizio (α_i)
    sorted_requests = sorted(requests, key=lambda r: parse_time_to_minutes(r["min_time_begin"]))

    # Ciclo greedy: per ogni richiesta, seleziona l'operatore migliore in base al costo
    for req in sorted_requests:
        
        alpha_i = parse_time_to_minutes(req["min_time_begin"])
        beta_i = parse_time_to_minutes(req["max_time_begin"])
        t_i = req["duration"]

        best_op = None
        best_cost = float("inf")

    
        for op in operators:
            travel_time = compute_travel_time(op, req, patients)
            hours_if_assigned = op["weekly_worked"] + (t_i + travel_time)
            # Salta se supera max_weekly_hours
            if hours_if_assigned > op["max_weekly_hours"]:
                continue

            # Controlla i vincoli (e_o + travel_time <= beta_i, t_i <= h_o)
            if op["eo"] + travel_time <= beta_i and t_i <= op["ho"]:
                cost = compute_cost(variant, op, t_i, travel_time)
                if cost < best_cost:
                    best_cost = cost
                    best_op = op

         # 4) Se ho trovato un operatore fattibile
        if best_op is not None:
            travel_time = compute_travel_time(best_op, req, patients)
            alpha_i = req["min_time_begin"]
            # e_o = max(e_o + tau, alpha_i) + t_i
            arrival_time = best_op["eo"] + travel_time
            begin_service = max(arrival_time, alpha_i)
            finish_time = begin_service + t_i

            # Aggiorno w_o e e_o
            best_op["wo"] += (t_i + travel_time)  # w_o = w_o + t_i + tau
            best_op["eo"] = finish_time  # e_o = finish_time

            # h_o = shift_end - e_o
            best_op["ho"] = shift_end - best_op["eo"]

            # p_o = p_i
            # Se hai la lista di pazienti e vuoi aggiornare lat/lon, puoi farlo qui
            best_op["current_patient"] = {"id": req["project_id"]}

            # Aggiungo la richiesta alla lista
            best_op["Lo"].append(req["id"])
            assignments.setdefault(best_op["id"], []).append(req["id"])


    return assignments





def is_operator_available(op, req):
    return True


def parse_time_to_minutes(time_value):
    """
    Converte un orario espresso nel formato H.MM (es. "15.55" per 15:55)
    in minuti. Ad esempio: "15.55" → 15*60 + 55 = 955 minuti.
    Se il valore non contiene il punto, lo interpreta come ore e lo converte in minuti.
    """
    s = str(time_value)
    if '.' in s:
        parts = s.split('.')
        hour = int(parts[0])
        minute = int(parts[1])
        return hour * 60 + minute
    else:
        return int(float(s) * 60)


def compute_travel_time(op, req, patients):
    """
    Calcola il tempo di spostamento (tau) utilizzando la matrice delle distanze.
    Si usano gli id globali: l'id dell'operatore e l'id del paziente.
    Poiché lavoriamo in minuti, non converto il valore.
    """
    patient = next((p for p in patients if p["id"] == req["project_id"]), None)
    if patient is None:
        return float("inf")
    return get_distance(op["id"], patient["id"])



def compute_cost(variant, op, t_i, tau):
    """
    Calcola il costo in base alla variante.
    - Time: minimizza tau
    - Saturami: minimizza ho_final => ho_final = op["ho"] - t_i => cost = ho_final
               (più piccolo => preferito => saturazione)
    - LasciamiInPace: massimizza ho_final => cost = -ho_final
    - TradeOff: minimizza w_o + tau + t_i
    """
    if variant == "Time":
        return tau
    elif variant == "Saturami":
        ho_final = op["ho"] - t_i
        return ho_final
    elif variant == "LasciamiInPace":
        ho_final = op["ho"] - t_i
        return -ho_final
    elif variant == "TradeOff":
        return op["wo"] + tau + t_i
    else:
        raise ValueError(f"Variante {variant} non valida")


def update_operator(op, req, patients):
    """
    Aggiorna lo stato dell'operatore dopo aver assegnato una richiesta:
      - Diminuisce il tempo disponibile (max_weekly_hours) in base alla durata della richiesta.
      - Aggiorna la posizione dell'operatore alla posizione del paziente.
    """
    op["max_weekly_hours"] -= op["wo"]
    patient = next((p for p in patients if p["id"] == req["project_id"]), None)
    if patient:
        op["lat"] = patient["lat"]
        op["lon"] = patient["lon"]


def display_assignments(assignments):
    data = []
    for op_id, req_list in assignments.items():
        data.append({
            "Operator ID": op_id,
            "Name": next(op["name"] for op in operators if op["id"] == op_id),
            "Surname": next(op["surname"] for op in operators if op["id"] == op_id),
            "Num Requests": len(req_list),
            "Request IDs": ", ".join(req_list)
        })
    df = pd.DataFrame(data)
    return df


def run_grs_for_week(variant, operators, requests, patients):
    """
    Esegue il GRS per 7 giorni, suddividendo in turni mattutino/pomeridiano
    e restituisce un dizionario con tutte le assegnazioni, oltre a lasciare
    nei campi degli operatori i dettagli su quanto hanno lavorato
    e quali richieste hanno preso nei turni mattina/pomeriggio.
    """
    all_assignments = {}


    for op in operators:
        op["worked_morning"] = False
        op["weekly_worked"] = 0  
        op["morning_requests"] = []
        op["afternoon_requests"] = []
        op["morning_minutes"] = 0
        op["afternoon_minutes"] = 0

    for day in range(7):
        # Filtra le richieste del giorno corrente
        day_requests = [r for r in requests if r["day"] == day]

        # ------ Turno mattutino ------
        for op in operators:
            set_operator_state_morning(op)
            
        morning_requests = [r for r in day_requests if parse_time_to_minutes(r["min_time_begin"]) < 720]

        assignments_morning = grs(variant, operators, morning_requests, patients, shift_end=720)

        for op_id, req_ids in assignments_morning.items():
            # Indica che questo operatore ha lavorato al mattino
            for op in operators:
                if op["id"] == op_id:
                    op["worked_morning"] = True
                    op["morning_requests"].extend(req_ids)

            all_assignments.setdefault(op_id, []).extend(req_ids)

        # Accumula i minuti effettivi lavorati al mattino, fino a un massimo di 300
        for op in operators:
            if op["eo"] > 420:  
                used_minutes = min(op["eo"] - 420, 300)
                op["morning_minutes"] += used_minutes
                op["weekly_worked"] += used_minutes

        # ------ Turno pomeridiano ------
        afternoon_requests = [r for r in day_requests if parse_time_to_minutes(r["min_time_begin"]) >= 720]

        for op in operators:
            set_operator_state_afternoon(op)

        assignments_afternoon = grs(variant, operators, afternoon_requests, patients, shift_end=1290)

        for op_id, req_ids in assignments_afternoon.items():
            for op in operators:
                if op["id"] == op_id:
                    op["afternoon_requests"].extend(req_ids)
            all_assignments.setdefault(op_id, []).extend(req_ids)

        # Accumula i minuti effettivi lavorati al pomeriggio, 
        for op in operators:
            # Pomeriggio inizia alle 16:00/18:00, dipende se ha lavorato al mattino o no
            # (viene controllato dal set_operator_state_afternoon). Usa op["eo"] finale.
            # Se e_o parte da 960 o 1080 e va fino a un massimo di 1290.
            # min() evita che superi 1290 - e_o_iniz (max 300 minuti)
            if op["eo"] > op["eo_start_afternoon"]:
                used_minutes = min(op["eo"] - op["eo_start_afternoon"], 300)
                op["afternoon_minutes"] += used_minutes
                op["weekly_worked"] += used_minutes

    return all_assignments


def display_assignments_with_shifts(operators):
    """
    Costruisce un DataFrame che mostra, per ciascun operatore:
    - Quante richieste ha fatto al mattino
    - Quante richieste ha fatto al pomeriggio
    - Il totale di minuti (o ore) lavorati in settimana
    - L'elenco di ID richieste mattina/pomeriggio
    """
    data = []
    for op in operators:
        data.append({
            "Operator ID": op["id"],
            "Name": op["name"],
            "Surname": op["surname"],
            "Morning Requests": ", ".join(op["morning_requests"]),
            "Afternoon Requests": ", ".join(op["afternoon_requests"]),
            "Num Morning": len(op["morning_requests"]),
            "Num Afternoon": len(op["afternoon_requests"]),
            "Morning Hours": round(op["morning_minutes"] / 60, 2),
            "Afternoon Hours": round(op["afternoon_minutes"] / 60, 2),
            "Total Hours": round(op["weekly_worked"] / 60, 2),
            "Max Weekly Hours": round(op["max_weekly_hours"] / 60, 2)
        })
    return pd.DataFrame(data)



variants = ["Time", "Saturami", "LasciamiInPace", "TradeOff"]

for variant in variants:
   
     # Esegue GRS completo su 7 giorni
    all_assignments = run_grs_for_week(variant, operators, requests, patients)
    
    # Genera un DataFrame con i dettagli di tutti i turni
    df = display_assignments_with_shifts(operators)

    # Salva come CSV
    results_dir = os.path.join(os.path.dirname(__file__), '..', 'variants_results')
    os.makedirs(results_dir, exist_ok=True)
    out_csv = os.path.join(results_dir, f"assignments_{variant}.csv")
    df.to_csv(out_csv, index=False)
    print(f"File '{out_csv}' salvato.")
