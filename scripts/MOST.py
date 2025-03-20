import csv
from typing import List, Dict
from utils import parse_time_to_minutes

def MOST(requests, session_start_minute: int, session_end_minute: int):
    """
    Calcola il numero massimo di operatori necessari contemporaneamente
    in una sessione (definita da orario di inizio/fine in minuti).

    :param requests: elenco delle richieste (lista di dict):
    :param session_start_minute: orario di inizio sessione in minuti (es: 540 = 9:00)
    :param session_end_minute: orario di fine sessione in minuti (es: 780 = 13:00)
    :return: intero, numero minimo di operatori richiesti nello stesso momento durante la sessione
    """
    # Calcola la durata in minuti e quanti "slot" di 10 minuti contiene
    session_duration = session_end_minute - session_start_minute
    n_s = session_duration // 10

    # T[i][t] = numero di operatori richiesti dalla i-esima richiesta
    #           allo slot t, se è attiva, altrimenti 0
    T = []

    for req in requests:
        alpha_i = parse_time_to_minutes(req['min_time_begin'])
        beta_i  = parse_time_to_minutes(req['max_time_begin'])   
        t_i     = req['duration']

        row = []
        for t in range(n_s + 1):
            time_slot = session_start_minute + (t * 10)
            
            if beta_i <= time_slot < (alpha_i + t_i):
                row.append(1)
            else:
                row.append(0)
        T.append(row)


    NO_t = [0] * (n_s + 1)
    for t in range(n_s + 1):
        NO_t[t] = sum(T[i][t] for i in range(len(T)))

    return max(NO_t)