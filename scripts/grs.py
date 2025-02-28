# Script utilizzato per implementare l'algoritmo 1 GRS

import datetime, math
from operators_requests import Operator, Request, Node
from typing import List, Optional, Tuple

def sort_requests_by_alpha(requests):
    """
    Ordina le richieste in base all'istante di inizio della finestra temporale.
    
    :param requests: Lista di oggetti Request.
    :return: Lista di oggetti Request ordinati.
    """
    return sorted(requests, key=lambda r: r.temporal_window[0])


## funzione per reimpostare lo stato di operatore per il turno pomeridiano (t0 = 960)
def reset_operator_state_afternoon(operator):
    """
    Reimposta lo stato dell'operatore per il turno pomeridiano.
    
    :param operator: Oggetto di tipo Operator.
    """
    operator.current_patient = operator.home
    operator.t0 = 960
    operator.work_time = 300


def compute_travel_time(node_a: Node, node_b: Node) -> float:
    """
    Calcola il tempo di viaggio tra due nodi usando la distanza euclidea.
    """
    dx = node_a.coordinates[0] - node_b.coordinates[0]
    dy = node_a.coordinates[1] - node_b.coordinates[1]
    # 1 unità di distanza = 1 minuto di viaggio
    return math.sqrt(dx**2 + dy**2)


def is_feasible(operator: Operator, request: Request) -> bool:
    """
    Verifica la fattibilità della richiesta per un operatore.
    Condizione: 
      αᵢ ≤ tₒ + τₚₒᵢ ≤ βᵢ  e  dᵢ + τₚₒᵢ ≤ wₒ
    """
    travel_time = compute_travel_time(operator.current_patient, request.patient)
    arrival_time = operator.t0 + travel_time
    alpha, beta = request.temporal_window

    # Controllo finestra temporale
    if not (alpha <= arrival_time <= beta):
        return False

    # Controllo tempo di lavoro residuo
    if (travel_time + request.duration) > operator.work_time:
        return False

    return True


def select_best_operator_for_request(request: Request,
                                     operators: List[Operator]) -> Optional[Operator]:
    """
    Sceglie, tra gli operatori, quello che minimizza τₚₒᵢ (tempo di viaggio)
    rispettando i vincoli di fattibilità. Se nessuno è fattibile, restituisce None.
    """
    feasible_ops = []
    for op in operators:
        # Calcola il travel time una sola volta per la selezione
        travel_time = compute_travel_time(op.current_patient, request.patient)
        if is_feasible(op, request):
            feasible_ops.append((op, travel_time))

    if not feasible_ops:
        return None

    # Tra gli operatori fattibili, seleziona quello con travel_time minimo
    best_operator, _ = min(feasible_ops, key=lambda x: x[1])
    return best_operator


def grs(operators: List[Operator],
        requests: List[Request]) -> dict:
    """
    Greedy Routing and Scheduling (GRS).
    1. Ordina le richieste per αᵢ
    2. Per ciascuna richiesta, trova l'operatore fattibile con min travel_time
    3. Aggiorna lo stato dell'operatore (wₒ, tₒ, pₒ)
    4. Ritorna uno schedule sotto forma di dict: {op_id: [richieste]}
    """
    # (1) Ordina le richieste per αᵢ
    sorted_requests = sorted(requests, key=lambda r: r.temporal_window[0])

    # (2) Inizializza uno schedule vuoto per ciascun operatore
    schedule = {op.id: [] for op in operators}

    # (3) Per ciascuna richiesta, trova l'operatore con min travel_time
    for req in sorted_requests:
        # Seleziona il miglior operatore per la richiesta
        chosen_op = select_best_operator_for_request(req, operators)
        
        if chosen_op is not None:
            # Calcola il tempo di viaggio tra il paziente attuale dell'operatore e il paziente della richiesta
            travel_time = compute_travel_time(chosen_op.current_patient, req.patient)

            # Aggiorna lo stato dell'operatore
            chosen_op.work_time -= (travel_time + req.duration)
            chosen_op.t0 += (travel_time + req.duration)
            chosen_op.current_patient = req.patient

            # Aggiunge la richiesta allo schedule dell'operatore
            schedule[chosen_op.id].append(req)
        else:
            print(f"Richiesta {req.i} non assegnabile a nessun operatore.")

    return schedule
