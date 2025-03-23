import datetime, math
import os, sys
import pandas as pd

from utils import parse_time_to_minutes, parse_minutes_to_hours
from typing import List, Optional, Tuple

# TOLTA MOMENTANEAMENTE LA SELEZIONE DELLA VARIANTE, DA RIAGGIUNGERE IN INPUT E AGGIUNGERE LE ALTRE VARIANTI E LOGICA DI SELEZIONE  
def grs_variants(operators, requests, patients, shift_end, down_time_true, tau, k):

   
    # print("[DEBUG] Inizio grs_variants: tau =", tau, type(tau))
    """
    Funzione unica per l'algoritmo GRS che, in base alla variante scelta,
    assegna le richieste agli operatori.

    ## Varianti disponibili:
    - "Time": Minimizza gli spostamenti tra i pazienti
    - "MaxTimeUse": Massimizza l’utilizzo del tempo disponibile, minimizzando il tempo residuo (ho)
    - "MinResidualTime": Massimizza il tempo residuo, lasciando più margine (-ho)
    - "TradeOff": Minimizza la somma tra lavoro accumulato, spostamento e durata (wo + tau + ti)

    :param variant: Nome della variante dell'algoritmo GRS.
    :param operators: Lista di operatori (dizionari).
    :param requests: Lista di richieste (dizionari).
    :param patients: cluster di pazienti (dizionari).
    :param shift_end: Orario di fine turno (in minuti).
    :return: Tuple con:
    - feasible: True se la soluzione trovata è ammissibile, False altrimenti.
    - total_routing_cost: Costo totale degli spostamenti.
    - total_overtime_cost: Costo totale degli straordinari.
    - total_waiting_time: Tempo totale di attesa.
    - not_used_ops: Lista degli operatori non utilizzati.
    """

    used_ops = []
    feasible = True
    assignments = {}
    total_routing_cost = 0
    total_overtime_cost = 0

    for p in patients:
        tau['h', p["id"]] = 0

    # Ordina le richieste per il tempo minimo di inizio (α_i)
    sorted_requests = sorted(requests, key=lambda r: parse_time_to_minutes(r["min_time_begin"]))

    # creo sorted_operators in modo che l'operatore a cui rimane più tempo da lavorare sia il primo 
    sorted_operators = sorted(operators, key=lambda o: o["Ho"] - o["wo"], reverse=True)

    tot_waiting_time = 0
    # Ciclo greedy: per ogni richiesta, seleziona l'operatore migliore in base al costo
    for req in sorted_requests:
        
        alpha_i = parse_time_to_minutes(req["min_time_begin"])
        beta_i = parse_time_to_minutes(req["max_time_begin"])

        best_op = None
        best_f_oi = float("inf")
        best_r_c = float("inf")
        best_ov_c = float("inf")
        waiting_time = {}

        for op in sorted_operators:
            waiting_time[op["id"]] = max(alpha_i - op["eo"] - tau[op["current_patient_id"], req["project_id"]], 0) if op["Lo_k"][k] else 0
    
        feasible_ops = [op for op in sorted_operators if op["eo"] + tau[op["current_patient_id"], req["project_id"]] <= beta_i and tau[op["current_patient_id"], req["project_id"]] + req["duration"] + waiting_time[op["id"]] <= op["ho"]]

        if len(feasible_ops) == 0:
            print(f"Richiesta {req['id']} non assegnata: nessun operatore disponibile.")
            print("Beta_i: ", beta_i, " Alpha_i: ", alpha_i, " Duration: ", req["duration"])
            print(""*5)
            # for op in sorted_operators:
            #     print(f"Operatore {op['id']}: eo = {op['eo']}, current_patient_id = {op['current_patient_id']}, ho = {op['ho']} tau = {tau[op['current_patient_id'], req['project_id']]}, waiting_time = {waiting_time[op['id']]}")

            feasible = False
           

        else:
            for op in feasible_ops:
                # Calcolo il travel time dalla posizione corrente dell'operatore al paziente della richiesta
                #travel_time = compute_travel_time(op, req["project_id"], patients)
                
                """
                Calcolo del waiting_time:
                - Se l'operatore ha già avuto almeno una richiesta assegnata (la lista op["Lo"] non è vuota),
                allora il waiting_time viene calcolato come:
                    waiting_time = max(alpha_i - (op["eo"] + travel_time), 0)
                - Altrimenti significa che l'operatore non ha ancora iniziato 
                a svolgere il servizio e dunque non si deve considerare il tempo d'attesa iniziale.
                In questo caso, waiting_time viene impostato a 0.
                """
               
                
                r_c, ov_c, f_oi = compute_f_oi(op, req, waiting_time[op["id"]], tau=tau, down_time_true=down_time_true)
                if f_oi < best_f_oi:
                    best_f_oi = f_oi
                    best_op = op
                    best_ov_c = ov_c
                    best_r_c = r_c


         # 4) Se ho trovato un operatore fattibile, aggiorno il suo stato e la richiesta
        if best_op is not None:
            travel_time = tau[best_op["current_patient_id"], req["project_id"]]


            # print("Request ", req["id"], " assigned to operator ", best_op["id"], " with f_oi = ", best_f_oi, " and waiting time = ", waiting_time[best_op["id"]])
            # input()

            # Calcolo dei tempi:
            # arrival_time: l'operatore arriva al paziente
            arrival_time = best_op["eo"]+ travel_time
            # b_i: inizio del servizio, momento in cui eroga la prestazione
            b_i = max(arrival_time, alpha_i)
            # finish_time: fine del servizio (prestazione)
            finish_time = b_i + req["duration"]

            # Aggiorno lo stato dell'operatore

            # wo = wo + (duration + travel_time)
            best_op["wo_k"][k] += req["duration"] + travel_time + waiting_time[best_op["id"]] # w_o = w_o + t_i + tau + d_o
            best_op["road_time_k"][k] += travel_time
            
            # eo = max{e_o + travel_time, α_i} + duration, ovvero finish_time
            best_op["eo"] = finish_time

            # h_o = shift_end - e_o, ovvero il tempo residuo del turno dell'operatore
            best_op["ho"] = shift_end - best_op["eo"]

            # p_o = p_i
            best_op["current_patient_id"] = req["project_id"]

            # aggiorno il tempo di attesa, d_o = d_o + waiting_time
            best_op["do_k"][k] += waiting_time[best_op["id"]]
            
            tot_waiting_time += waiting_time[best_op["id"]]

            # Aggiungo la richiesta alla lista
            best_op["Lo_k"][k].append((req, b_i)) # Lo = Lo U (i,b_i)
            # [DEBUG] print(f"[DEBUG grs_variants] Operatore {best_op['id']} global_assignments: {best_op['global_assignments']}")

            # segno quanto overtime ha fatto l'operatore
            best_op["overtime_minutes_k"][k] = max(best_op["wo_k"][k] - best_op["Ho"], 0)

            req["b_i"] = b_i

            # se b_i, inizio del servizio, è dopo le 11:30 e la richiesta non può iniziare dopo le 12:30
            # allora l'operatore ha lavorato un turno pieno la mattina e non può fare doppio turno
            # if b_i >= 11*60 + 30 and req["min_time_begin"] < 12*60 + 30:
            #     #Aggiungo che best op ha lavorato turno pieno la mattina e in questo giorno non può fare doppio turno
            #     best_op["worked_after_11:30am"] = True

            used_ops.append(best_op["id"])

            if b_i >= 11*60 + 30 and alpha_i < 12*60 + 30:
                best_op["worked_after_11:30am_k"][k] = True

            

            # Aggiorno il costo totale
            total_routing_cost += best_r_c
            total_overtime_cost += best_ov_c
    
    operators_id = [op["id"] for op in operators]
    not_used_ops = [op for op in operators_id if op not in used_ops]

    return feasible, total_routing_cost, total_overtime_cost, sum(op["do_k"][k] for op in operators), not_used_ops

###############################################################################
# Funzione per calcolare il costo extra (f_oi) dell'assegnazione
###############################################################################

def compute_f_oi(operator, request, waiting_time, theta=0.37, tau=None, down_time_true=False):
    """
    Calcola il valore f_oi per l'assegnazione della richiesta all'operatore.

    f_oi è definito come:
        theta * travel_time + overtime_penalty + theta^2 * waiting_time   se l'assegnazione porta in overtime (x_oi = 1)
        theta * travel_time + theta^2 * waiting_time                      altrimenti

    overtime_penalty viene calcolata così:
       - Se operator.w_o < operator.H_o: overtime_minutes = operator.w_o - operator.H_o + request.duration + travel_time 
       - Se operator.w_o >= operator.H_o: overtime_minutes = 0 + request.duration + travel_time

    
       :param operator: oggetto Operator con attributi wo (w_o, tempo già lavorato), Ho (H_o, limite massimo in minuti),
                 C_o (costo al minuto dell'operatore) e current_patient_id (posizione corrente).
       :param request: oggetto Request con attributo duration e project_id (nodo del paziente).
       :param theta: coefficiente relativo al costo di spostamento (rimborso per il tempo di viaggio).

    Ritorna:
       f_oi: valore del costo extra per l'assegnazione della richiesta, che include il costo di spostamento e
             il costo overtime, se applicabile.
    """
    if tau is None:
        raise ValueError("La matrice dei tempi di viaggio (tau) è richiesta per calcolare il costo f_oi.")
    
    # Calcolo il tempo di spostamento tra la posizione corrente dell'operatore e il paziente della richiesta
    travel_time = tau[operator["current_patient_id"], request["project_id"]]
    service_time = request["duration"]

    # Verifico se assegnare la richiesta porta l'operatore in overtime con waiting_time
    if operator["wo"] + service_time + travel_time + waiting_time > operator["Ho"]:
        op_cost_per_minute = 0.29 # C_o, 17.5 €/h, quindi 0.29 €/min
        
        overtime_cost = op_cost_per_minute * (service_time + travel_time + waiting_time+min(operator["wo"] - operator["Ho"], 0))
    else:
        overtime_cost = 0

    if down_time_true:
        d_t_t = 1
    else:    
        d_t_t = 0

    routing_cost = theta * travel_time
    waiting_cost = ((theta**2) * waiting_time) * d_t_t
    #waiting_cost = 100*waiting_time * d_t_t



    f_oi = routing_cost + overtime_cost + waiting_cost

    return routing_cost, overtime_cost, f_oi
