import datetime, math
import os, sys
import pandas as pd
from operators_requests import Operator, Request, Node
from typing import List, Optional, Tuple

scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_path)

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

# MATTINA
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

    shift_end = 1320 # 22:00 with 30 minutes of overtime

# POMERIGGIO
def set_operator_state_morning(operator):
    """
    Reimposta lo stato dell'operatore per il turno mattutino.
    Il turno mattutino inizia alle 7:00 (420 minuti).
    """
    operator["eo"] = 420
    operator["ho"] = 330
    operator["wo"] = 0
    operator["Lo"] = [] # lista delle richieste assegnate all'operatore
    operator["x_oi"] = 0 # 1 se assegnando la richiesta i all'operatore o, questo va in overtime

    shift_end = 750 # 12:30 with 30 minutes of overtime

def grs(variant, operators, requests, patients, shift_end):
    """
    Funzione unica per l'algoritmo GRS che, in base alla variante scelta,
    assegna le richieste agli operatori.

    :param variant: Nome della variante dell'algoritmo GRS.
    :param operators: Lista di operatori (dizionari).
    :param requests: Lista di richieste (dizionari).
    :param patients: Lista di pazienti (dizionari).
    :param shift_end: Orario di fine turno (in minuti).
    :return: Un dizionario con le assegnazioni (operatore -> richieste).
    """

    assignments = {}


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
            # Calcolo il travel time dalla posizione corrente dell'operatore al paziente della richiesta
            travel_time = compute_travel_time(op["current_patient_id"], req["project_id"])
            
            # hours_if_assigned = op["weekly_worked"] + (t_i + travel_time)
            # # Salta se supera max_weekly_minutes
            # if hours_if_assigned > op["max_weekly_minutes"]:
            #     continue


            # Condizione 1: l'orario di inizio (eo) più il travel time non supera max_time_begin
            if op["eo"] + travel_time > req["max_time_begin"]:
                continue

            # Condizione 2: il tempo totale richiesto (travel_time + durata della visita + eventuale waiting)
            # deve essere minore o uguale al tempo residuo (ho) dell'operatore.
            waiting_time = max(req["min_time_begin"] - op["eo"] - travel_time, 0)
            if travel_time + req["duration"] + waiting_time > op["ho"]:
                continue
            
            f_oi = compute_f_oi(op, req)
            if f_oi < best_f_oi:
                best_f_oi = f_oi
                best_op = op

         # 4) Se ho trovato un operatore fattibile, aggiorno il suo stato e la richiesta
        if best_op is not None:
            travel_time = compute_travel_time(best_op["current_patient_id"], req["project_id"])

            alpha_i = req["min_time_begin"]

            # Calcolo dei tempi:
            # arrival_time: l'operatore arriva al paziente
            arrival_time = best_op["eo"] + travel_time
            # b_i: inizio del servizio, momento in cui eroga la prestazione
            b_i = max(arrival_time, alpha_i)
            # finish_time: fine del servizio (prestazione)
            finish_time = b_i + req["duration"]

            # Aggiorno lo stato dell'operatore

            # weekly_worked = weekly_worked + (duration + travel_time)
            best_op["weekly_worked"] += req["duration"] + travel_time # w_o = w_o + t_i + tau
            
            # eo = max{e_o + travel_time, α_i} + duration, ovvero finish_time
            best_op["eo"] = finish_time

            # h_o = shift_end - e_o
            best_op["ho"] = shift_end - best_op["eo"]

            # p_o = p_i
            best_op["current_patient_id"] = req["project_id"]

            # Aggiungo la richiesta alla lista
            best_op["Lo"].append(req["id"], b_i) # Lo = Lo U (i,b_i)
            assignments.setdefault(best_op["id"], []).append(req["id"])

            req["b_i"] = b_i # per analisi successive?

    return assignments


def compute_f_oi(operator, request, theta=0.37):
    """
    Calcola il valore f_oi per l'assegnazione della richiesta all'operatore.

    f_oi è definito come:
         f_oi = theta * travel_time + overtime_penalty   se l'assegnazione porta in overtime (x_oi = 1)
                0                                        altrimenti

    Dove overtime_penalty si calcola come:
       - Se operator.w_o < operator.H_o: overtime_minutes = operator.w_o + request.duration + travel_time - operator.H_o
       - Se operator.w_o >= operator.H_o: overtime_minutes = request.duration + travel_time

    Parametri:
       operator: oggetto Operator con attributi weekly_worked (w_o, tempo già lavorato), max_weekly_minutes (H_o, limite massimo in minuti),
                 C_o (costo al minuto) e current_patient_id (posizione corrente).
       request: oggetto Request con attributo duration e project_id (nodo del paziente).
       theta: coefficiente relativo al costo di spostamento (rimborso per il tempo di viaggio).

    Ritorna:
       f_oi: valore del costo extra per l'assegnazione della richiesta, che include il costo di spostamento e
             il costo overtime, se applicabile.
    """
    # Calcola il tempo di spostamento tra la posizione corrente dell'operatore e il paziente della richiesta
    travel_time = compute_travel_time(operator.current_patient_id, request.project_id)
    service_time = request.duration

    # Verifica se assegnare la richiesta porta l'operatore in overtime
    if operator.weekly_worked + service_time + travel_time > operator.max_weekly_minutes:
        # x_oi = 1: overtime attivo
        if operator.weekly_worked < operator.max_weekly_minutes:
            # Caso 2: l'operatore non era già in overtime
            # si paga overtime solo per l'eccedenza rispetto a max_weekly_minutes.
            overtime_minutes = operator.weekly_worked + service_time + travel_time - operator.max_weekly_minutes
        else:
            # Caso 1: l'operatore era già in overtime, si paga per l'intero tempo aggiuntivo
            overtime_minutes = service_time + travel_time
        
        op_cost_per_minute = 0.29 # C_o, 17.5 €/h, quindi 0.29 €/min
        
        overtime_penalty = op_cost_per_minute * overtime_minutes
    else:
        overtime_penalty = 0

    f_oi = theta * travel_time + overtime_penalty

    return f_oi


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
    
    if op["current_patient_id"] is None:
        # Prima richiesta: distanza da casa dell'operatore al paziente
        operator_id_for_distance = op["id"] + 248
    else:
        # Richieste successive: distanza dal paziente precedente al paziente corrente
        operator_id_for_distance = op["current_patient_id"]

    return get_distance(operator_id_for_distance, patient["id"])



# def compute_cost(variant, op, t_i, tau):
#     """
#     Calcola il costo in base alla variante.
#     - Time: minimizza tau
#     - Saturami: minimizza ho_final => ho_final = op["ho"] - t_i => cost = ho_final
#                (più piccolo => preferito => saturazione)
#     - LasciamiInPace: massimizza ho_final => cost = -ho_final
#     - TradeOff: minimizza w_o + tau + t_i
#     """
#     if variant == "Time":
#         return tau
#     elif variant == "Saturami":
#         ho_final = op["ho"] - t_i
#         return ho_final
#     elif variant == "LasciamiInPace":
#         ho_final = op["ho"] - t_i
#         return -ho_final
#     elif variant == "TradeOff":
#         return op["wo"] + tau + t_i
#     else:
#         raise ValueError(f"Variante {variant} non valida")


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


# non c'è priorità di assegnazione tra chi ha lavorato di più e chi ha lavorato di meno

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

        # Accumula i minuti effettivi lavorati al mattino, fino a un massimo di 330 (300 + overtime)
        for op in operators:
            if op["eo"] > 420:  
                used_minutes = min(op["eo"] - 420, 330) # CONTROLLARE
                op["morning_minutes"] += used_minutes
                # op["weekly_worked"] += used_minutes

        # ------ Turno pomeridiano ------
        afternoon_requests = [r for r in day_requests if parse_time_to_minutes(r["min_time_begin"]) >= 720]

        for op in operators:
            set_operator_state_afternoon(op)

        assignments_afternoon = grs(variant, operators, afternoon_requests, patients, shift_end=1320)

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
            # min() evita che superi 1290 (21:30) - e_o_iniz, max 300
            if op["eo"] > op["eo_start_afternoon"]:
                used_minutes = min(op["eo"] - op["eo_start_afternoon"], 300)
                op["afternoon_minutes"] += used_minutes
                # op["weekly_worked"] += used_minutes

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
            "Num Req Morning": len(op["morning_requests"]),
            "Num Req Afternoon": len(op["afternoon_requests"]),
            "Morning Hours Worked": round(op["morning_minutes"] / 60, 2),
            "Afternoon Hours Worked": round(op["afternoon_minutes"] / 60, 2),
            "Total Hours": round(op["weekly_worked"] / 60, 2),
            "Max Weekly Hours": round(op["max_weekly_minutes"] / 60, 2)
        })
    return pd.DataFrame(data)



# variants = ["Time", "Saturami", "LasciamiInPace", "TradeOff"]

variants = ["TradeOff"]
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
