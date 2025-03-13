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
tau = {}

with open(json_path, "r") as f:
    tau = eval(f.read())


###############################################################################
# Funzioni di setup dei turni
###############################################################################

# POMERIGGIO
def set_operator_state_afternoon(operator):
    """
    Reimposta lo stato dell'operatore per il turno pomeridiano.
    - Se l'operatore ha lavorato dopo le 11:30 (worked_after_11:30am == True),
      il turno pomeridiano inizia alle 18:00 (1080 minuti).
    - Se l'operatore ha lavorato al mattino (worked_morning == True) ma non dopo le 11:30,
      il turno pomeridiano inizia alle 16:00 (960 minuti).
    - Se l'operatore non ha lavorato al mattino, inizia comunque alle 16:00 (960 minuti) 
      e con un turno di 5 ore (300 minuti disponibili).
    """
    if operator.get("worked_after_11:30am", False):
        operator["eo_start_afternoon"] = 1080
        operator["eo"] = 1080
        operator["ho"] = 240
    elif operator.get("worked_morning", False):
        operator["eo_start_afternoon"] = 960
        operator["eo"] = 960
        operator["ho"] = 360
    else:
        operator["eo_start_afternoon"] = 960
        operator["eo"] = 960
        operator["ho"] = 300

    operator["Lo"] = []
    operator["current_patient_id"] = 'h'

# MATTINA
def set_operator_state_morning(operator):
    """
    Reimposta lo stato dell'operatore per il turno mattutino.
    Il turno mattutino inizia alle 7:00 (420 minuti).
    """
    operator["eo"] = 420
    operator["ho"] = 330
    operator["Lo"] = [] # lista delle richieste assegnate all'operatore
    operator["current_patient_id"] = 'h'


###############################################################################
# Funzione GRS per l'assegnazione delle richieste
###############################################################################

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

    for p in patients:
        tau['h', p["id"]] = 0

    # Ordina le richieste per il tempo minimo di inizio (α_i)
    sorted_requests = sorted(requests, key=lambda r: parse_time_to_minutes(r["min_time_begin"]))

    # creo sorted_operators in modo che l'operatore a cui rimane più tempo da lavorare sia il primo 
    sorted_operators = sorted(operators, key=lambda o: o["max_weekly_minutes"] - o["weekly_worked"], reverse=True)

    # Ciclo greedy: per ogni richiesta, seleziona l'operatore migliore in base al costo
    for req in sorted_requests:
        
        alpha_i = parse_time_to_minutes(req["min_time_begin"])
        beta_i = parse_time_to_minutes(req["max_time_begin"])

        best_op = None
        best_f_oi = float("inf")

    
        for op in sorted_operators:
            # Calcolo il travel time dalla posizione corrente dell'operatore al paziente della richiesta
            #travel_time = compute_travel_time(op, req["project_id"], patients)
            travel_time = tau[op["current_patient_id"], req["project_id"]]


            # Condizione 1: l'orario di inizio (eo) più il travel time non supera max_time_begin
            if op["eo"] + travel_time > beta_i:
                continue


            """
            Calcolo del waiting_time:
            - Se l'operatore ha già avuto almeno una richiesta assegnata (la lista op["Lo"] non è vuota),
              allora il waiting_time viene calcolato come:
                  waiting_time = max(alpha_i - (op["eo"] + travel_time), 0)
            - Altrimenti significa che l'operatore non ha ancora iniziato 
              a svolgere il servizio e dunque non si deve considerare il tempo d'attesa iniziale.
              In questo caso, waiting_time viene impostato a 0.
            """
            if op["Lo"]:
                waiting_time = max(alpha_i - op["eo"] - travel_time, 0)
            else:
                waiting_time = 0

        
            # Condizione 2: il tempo totale richiesto (travel_time + durata della visita + eventuale waiting)
            # deve essere minore o uguale al tempo residuo (ho) dell'operatore.
            if travel_time + req["duration"] + waiting_time > op["ho"]:
                continue
            
            f_oi = compute_f_oi(op, req, waiting_time)
            if f_oi < best_f_oi:
                best_f_oi = f_oi
                best_op = op

         # 4) Se ho trovato un operatore fattibile, aggiorno il suo stato e la richiesta
        if best_op is not None:
            travel_time = tau[best_op["current_patient_id"], req["project_id"]]


            # Calcolo dei tempi:
            # arrival_time: l'operatore arriva al paziente
            arrival_time = best_op["eo"] + travel_time
            # b_i: inizio del servizio, momento in cui eroga la prestazione
            b_i = max(arrival_time, alpha_i)
            # finish_time: fine del servizio (prestazione)
            finish_time = b_i + req["duration"]

            # Aggiorno lo stato dell'operatore

            # weekly_worked = weekly_worked + (duration + travel_time)
            best_op["weekly_worked"] += req["duration"] + travel_time + waiting_time # w_o = w_o + t_i + tau + d_o
            best_op["road_time"] += travel_time
            
            # eo = max{e_o + travel_time, α_i} + duration, ovvero finish_time
            best_op["eo"] = finish_time

            # h_o = shift_end - e_o
            best_op["ho"] = shift_end - best_op["eo"]

            # p_o = p_i
            best_op["current_patient_id"] = req["project_id"]

            # aggiorno il tempo di attesa, d_o = d_o + waiting_time
            best_op["d_o"] += waiting_time 

            # Aggiungo la richiesta alla lista
            best_op["Lo"].append((req["id"], b_i)) # Lo = Lo U (i,b_i)
            assignments.setdefault(best_op["id"], []).append(req["id"])

            req["b_i"] = b_i # analisi successive?

    return assignments 

###############################################################################
# Funzione per calcolare il costo extra (f_oi) dell'assegnazione
###############################################################################

def compute_f_oi(operator, request, waiting_time, theta=0.37):
    """
    Calcola il valore f_oi per l'assegnazione della richiesta all'operatore.

    f_oi è definito come:
         f_oi = theta * travel_time + overtime_penalty   se l'assegnazione porta in overtime (x_oi = 1)
                theta * travel_time                      altrimenti

    overtime_penalty viene calcolata così:
       - Se operator.w_o < operator.H_o: overtime_minutes = operator.w_o - operator.H_o + request.duration + travel_time 
       - Se operator.w_o >= operator.H_o: overtime_minutes = 0 + request.duration + travel_time

    Parametri:
       operator: oggetto Operator con attributi weekly_worked (w_o, tempo già lavorato), max_weekly_minutes (H_o, limite massimo in minuti),
                 C_o (costo al minuto dell'operatore) e current_patient_id (posizione corrente).
       request: oggetto Request con attributo duration e project_id (nodo del paziente).
       theta: coefficiente relativo al costo di spostamento (rimborso per il tempo di viaggio).

    Ritorna:
       f_oi: valore del costo extra per l'assegnazione della richiesta, che include il costo di spostamento e
             il costo overtime, se applicabile.
    """
    # Calcolo il tempo di spostamento tra la posizione corrente dell'operatore e il paziente della richiesta
    travel_time = tau[operator["current_patient_id"], request["project_id"]]
    service_time = request["duration"]

    # Verifico se assegnare la richiesta porta l'operatore in overtime con waiting_time
    if operator["weekly_worked"] + service_time + travel_time + waiting_time > operator["max_weekly_minutes"]:
        op_cost_per_minute = 0.29 # C_o, 17.5 €/h, quindi 0.29 €/min
        
        overtime_penalty = op_cost_per_minute * (service_time + travel_time + min(operator["weekly_worked"] - operator["max_weekly_minutes"], 0))
    else:
        overtime_penalty = 0

    f_oi = theta * travel_time + overtime_penalty

    return f_oi

###############################################################################
# Funzioni per la conversione dei tempi
###############################################################################

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

def parse_minutes_to_hours(time_value):
    """
    Converte un valore espresso in minuti in ore e minuti.
    Ad esempio: 955 minuti → "15.55".
    """
    total = int(round(time_value))
    hours = total // 60
    minutes = total % 60
    
    return f"{hours}:{minutes:02d}"
    


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


###############################################################################
# Funzione GRS_WEEK: esecuzione GRS per la settimana
###############################################################################

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
        op["worked_after_11:30am"] = False
        op["morning_requests"] = []
        op["afternoon_requests"] = []
        op["morning_minutes"] = 0 
        op["afternoon_minutes"] = 0 
        op["d_o"] = 0 # tempo totale di attesa tra una richiesta e l'altra per l'operatore
        op["road_time"] = 0 # tempo totale di spostamento per l'operatore

    for day in range(7):
        # Filtra le richieste del giorno corrente
        day_requests = [r for r in requests if r["day"] == day]

        # ------ Turno mattutino ------
        shift_start = 420 # 7:00
        shift_end = 750 # 12:30

        for op in operators:
            set_operator_state_morning(op)
            
        morning_requests = [r for r in day_requests if parse_time_to_minutes(r["min_time_begin"]) < shift_end] # 12:30
        assignments_morning = grs(variant, operators, morning_requests, patients, shift_end)

        for op_id, req_ids in assignments_morning.items():
            for op in operators:
                if op["id"] == op_id:
                    op["worked_morning"] = True
                    op["morning_requests"].extend(req_ids)
                    if op["eo"] > 690:
                        op["worked_after_11:30am"] = True

        all_assignments.setdefault(op_id, []).extend(req_ids)

        # Accumula i minuti lavorati al mattino (limite massimo 330 minuti)
        for op in operators:
            if op["eo"] >= shift_start:
                worked = op["eo"] - shift_start
                op["morning_minutes"] += min(worked, 330)


        # ------ Turno pomeridiano ------
        afternoon_requests = [r for r in day_requests if parse_time_to_minutes(r["min_time_begin"]) >= 750]

        for op in operators:
            set_operator_state_afternoon(op)

        assignments_afternoon = grs(variant, operators, afternoon_requests, patients, shift_end=1320)

        for op_id, req_ids in assignments_afternoon.items():
            for op in operators:
                if op["id"] == op_id:
                    op["afternoon_requests"].extend(req_ids)
            all_assignments.setdefault(op_id, []).extend(req_ids)

        # Accumula i minuti lavorati al pomeriggio (limite massimo 300 minuti)
        for op in operators:
            if op["eo"] >= op["eo_start_afternoon"]:
                worked = op["eo"] - op["eo_start_afternoon"]
                op["afternoon_minutes"] += min(worked, 300)
                

    return all_assignments

###############################################################################
# Funzione per il reporting
###############################################################################


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
            "Morning Requests List": ", ".join(map(str, op["morning_requests"])),
            "Afternoon Requests List": ", ".join(map(str, op["afternoon_requests"])),
            "Num Req Morning": len(op["morning_requests"]),
            "Num Req Afternoon": len(op["afternoon_requests"]),
            # "Morning Hours Worked": parse_minutes_to_hours(op["morning_minutes"]),
            # "Afternoon Hours Worked": parse_minutes_to_hours(op["afternoon_minutes"]),
            "Total Hours Worked": parse_minutes_to_hours(op["weekly_worked"]),
            "Max Weekly Hours": parse_minutes_to_hours(op["max_weekly_minutes"]),
            "Road Time": parse_minutes_to_hours(op["road_time"]),
            "Waiting Time": parse_minutes_to_hours(op["d_o"])
        })
    return pd.DataFrame(data)

def display_global_statistics(operators):
    """
    Calcola alcune statistiche globali dai dati dei singoli operatori:
      - Total Requests: somma delle richieste mattutine e pomeridiane eseguite
      - Total Waiting Time: somma totale del waiting time (in formato H.MM)
      - Total Road Time: somma dei tempi di spostamento
      - Average Waiting Time: media dei waiting time degli operatori
      - Average Road Time: media dei road time degli operatori
    """
    total_requests = sum(len(op["morning_requests"]) + len(op["afternoon_requests"]) for op in operators)
    total_waiting = sum(op["d_o"] for op in operators)
    total_road = sum(op["road_time"] for op in operators)
    avg_waiting = total_waiting / len(operators) if operators else 0
    avg_road = total_road / len(operators) if operators else 0

    stats = {
        "Total Requests": total_requests,
        "Total Waiting Time": parse_minutes_to_hours(total_waiting),
        "Total Road Time": parse_minutes_to_hours(total_road),
        "Average Waiting Time": parse_minutes_to_hours(avg_waiting),
        "Average Road Time": parse_minutes_to_hours(avg_road)
    }
    return pd.DataFrame([stats])

###############################################################################
# Main: esecuzione e salvataggio dei risultati
###############################################################################

variants = ["TradeOff"]
for variant in variants:
   
     # Esegue GRS completo su 7 giorni
    all_assignments = run_grs_for_week(variant, operators, requests, patients)
    
    # Genera un DataFrame con i dettagli di tutti i turni per ogni operatore
    df_details = display_assignments_with_shifts(operators)
    
    # Genera un DataFrame con le statistiche globali
    df_stats = display_global_statistics(operators)
    
    # Salva il CSV dei dettagli
    results_dir = os.path.join(os.path.dirname(__file__), '..', 'variants_results')
    os.makedirs(results_dir, exist_ok=True)
    out_csv_details = os.path.join(results_dir, f"assignments_{variant}.csv")
    df_details.to_csv(out_csv_details, index=False)
    print(f"File '{out_csv_details}' salvato.")
    
    # Salva un CSV separato con le statistiche globali
    out_csv_stats = os.path.join(results_dir, f"global_stats_{variant}.csv")
    df_stats.to_csv(out_csv_stats, index=False)
    print(f"File '{out_csv_stats}' salvato.")
