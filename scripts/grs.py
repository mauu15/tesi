# Script utilizzato per implementare l'algoritmo 1 GRS - Time

import datetime, math
from operators_requests import Operator, Request, Node
from typing import List, Optional, Tuple

# funzione per ordinare le richieste in base all'istante di inizio della finestra temporale
def sort_requests_by_alpha(requests):
    """
    Ordina le richieste in base all'istante di inizio della finestra temporale.
    
    :param requests: Lista di oggetti Request.
    :return: Lista di oggetti Request ordinati.
    """
    return sorted(requests, key=lambda r: r.temporal_window[0])

# funzione per impostare lo stato di operatore per il turno mattutino (eo = 420)
def set_operator_state_morning(operator):
    """
    Reimposta lo stato dell'operatore per il turno mattutino.
    
    :param operator: Oggetto di tipo Operator.
    """
    operator.current_patient = operator.home
    operator.eo = 420 # Inizio turno mattutino: 7:00
    operator.ho = 300 # Tempo residuo disponibile: 5 ore
    operator.wo = 0 # tempo di lavoro accumulato
    operator.Lo = [] # Lista di richieste assegnate, inizialmente vuota


## funzione per impostare lo stato di operatore per il turno pomeridiano (eo = 960)
def set_operator_state_afternoon(operator):
    """
    Reimposta lo stato dell'operatore per il turno pomeridiano.
    
    :param operator: Oggetto di tipo Operator.
    """
    operator.current_patient = operator.home
    operator.eo = 960 # Inizio turno pomerdiano: 16:00
    operator.ho = 300 # Tempo residuo disponibile: 5 ore
    operator.wo = 0 # tempo di lavoro accumulato
    operator.Lo = [] # Lista di richieste assegnate, inizialmente vuota

# funzione per calcolare il tempo di viaggio tra due nodi
def compute_travel_time(node_a: Node, node_b: Node) -> float:
    """
    Calcola il tempo di viaggio tra due nodi usando la distanza euclidea.
    """
    dx = node_a.coordinates[0] - node_b.coordinates[0]
    dy = node_a.coordinates[1] - node_b.coordinates[1]
    # 1 unità di distanza = 1 minuto di viaggio
    return math.sqrt(dx**2 + dy**2)

# funzione per verificare la fattibilità di una richiesta per un operatore
def is_feasible(operator: Operator, request: Request, shift_end: int, debug: bool) -> Tuple[bool, Optional[str]]:
    """
    Verifica la fattibilità della richiesta per un operatore.
    Condizione: 
      eₒ + τₚₒₚᵢ ≤ βᵢ  e  dᵢ ≤ hₒ
    Restituisce:
      - (True, None) se fattibile
      - (False, "arrival") se il problema è l'orario di arrivo
      - (False, "work") se il problema è il tempo di lavoro residuo  
    """
    
    travel_time = compute_travel_time(operator.current_patient, request.patient)
    arrival_time = operator.eo + travel_time
    alpha, beta = request.temporal_window

    
    if arrival_time > beta:
        if debug:
            print(f"Richiesta {request.i} rifiutata per l'operatore {operator.id}:")
            print(f"  Arrival time = {arrival_time:.2f} non rientra in finestra ({alpha}, {beta})")
        return False, "arrival"
    
    if operator.eo + travel_time + request.duration > shift_end:
        if debug:
            print(f"Richiesta {request.i} rifiutata per l'operatore {operator.id}:")
            print(f"  supererebbe la fine del turno (eo + travel + duration = {operator.eo + travel_time + request.duration:.2f} > {shift_end})")
        return False, "work"
    
    if travel_time + request.duration > operator.ho:
        if debug:
            print(f"Richiesta {request.i} rifiutata per l'operatore {operator.id}:")
            print(f"  (Travel time + Durata) = {travel_time + request.duration:.2f} > Tempo rimanente ho = {operator.ho:.0f}")
        return False, "work"
    
    return True, None

# funzione per selezionare il miglior operatore per una richiesta
def select_best_operator_for_request(request: Request, operators: List[Operator], shift_end: int) -> Optional[Operator]:
    """
    Seleziona l'operatore che minimizza il travel time (τₚₒᵢ) tra quelli
    appartenenti al cluster della richiesta. Se nessun operatore è fattibile,
    restituisce None.
    """
    # Filtra gli operatori in base al cluster della richiesta
    relevant_ops = filter_operators_by_cluster(request, operators)
    
    feasible_ops = []
    for op in relevant_ops:
        travel_time = compute_travel_time(op.current_patient, request.patient)
        if is_feasible(op, request, shift_end, debug=False)[0]:
            feasible_ops.append((op, travel_time))
    
    if not feasible_ops:
        return None

    best_operator, _ = min(feasible_ops, key=lambda x: x[1])
    return best_operator


# funzione per eseguire il GRS
def grs_time(operators: List[Operator],
             requests: List[Request],
             is_morning: bool = True) -> Tuple[dict[int, List[Request]], dict[str, float]]:
    """
    Greedy Routing and Scheduling (GRS).
    1. Ordina le richieste per αᵢ
    2. Per ciascuna richiesta, trova l'operatore fattibile con min travel_time
    3. Aggiorna lo stato dell'operatore (ho, eo, wo, current_patient e Lo)
    4. Ritorna uno schedule e le statistiche del processo di scheduling

    Il parametro is_morning controlla il turno da simulare:
      - True: turno mattutino (shift_end = 720)
      - False: turno pomeridiano (shift_end = 1290, con reset dello stato)

    Restituisce una tupla con due elementi:
        - Uno schedule sotto forma di dict: {op_id: [richieste]}
        - Un dizionario con le statistiche del processo di scheduling

    Le statistiche includono:
      - total_requests: numero totale di richieste elaborate
      - assigned: numero di richieste assegnate
      - not_assigned: numero di richieste non assegnate
      - arrival_fail: numero di richieste non assegnate per arrival time non rispettato
      - work_fail: numero di richieste non assegnate per work time non rispettato
    """

     # Imposta shift_end in base al turno
    if is_morning:
        shift_end = 720  # turno mattutino
        for op in operators:
            set_operator_state_morning(op)
    else:
        shift_end = 1290  # turno pomeridiano
        # set dello stato per il turno pomeridiano
        for op in operators:
            set_operator_state_afternoon(op)

    # (1) Ordina le richieste per αᵢ
    sorted_requests = sorted(requests, key=lambda r: r.temporal_window[0])

    # (2) Inizializza uno schedule vuoto per ciascun operatore
    schedule = {op.id: [] for op in operators}
    stats = {
        'total_requests': len(sorted_requests),
        'assigned': 0,
        'not_assigned': 0,
        'arrival_fail': 0, # richieste non assegnate per arrival time non rispettato
        'work_fail': 0 # richieste non assegnate per work time non rispettato
    }

    # (3) Per ciascuna richiesta, trova l'operatore con min travel_time
    for req in sorted_requests:
        # Seleziona il miglior operatore per la richiesta
        chosen_op = select_best_operator_for_request(req, operators, shift_end)
        
        # Se non è possibile assegnare la richiesta, imposta chosen_op a None
        if chosen_op is not None and chosen_op.ho <= 0:
            chosen_op = None
        
        if chosen_op is not None:
            # Calcola il tempo di viaggio tra il paziente attuale dell'operatore e il paziente della richiesta
            travel_time = compute_travel_time(chosen_op.current_patient, req.patient)

            # Calcola l'istante di inizio servizio: s = max(eo + travel, αᵢ)
            s = max(chosen_op.eo + travel_time, req.temporal_window[0])

            # Aggiorna la lista delle richieste assegnate (Lo)
            # Lo tiene traccia delle assegnazioni come tuple: (richiesta, istante di inizio servizio)
            chosen_op.Lo.append((req, s))

            # Aggiorna il tempo di lavoro accumulato (wo)
            chosen_op.wo += travel_time + req.duration

            # Aggiorna il primo istante disponibile per servire la prossima richiesta (eo)
            chosen_op.eo = s + req.duration

            # Aggiorna il tempo residuo del turno (ho): shift_end - eo
            chosen_op.ho = shift_end - chosen_op.eo

            # Aggiorna il current patient: l'operatore si sposta presso il paziente della richiesta
            chosen_op.current_patient = req.patient
            
            # Aggiunge la richiesta allo schedule dell'operatore
            schedule[chosen_op.id].append(req)
            stats['assigned'] += 1
        else:
            # La richiesta non è assegnabile: aggiorna il contatore
            stats['not_assigned'] += 1
            # Per capire il motivo, esamina gli operatori rilevanti
            reasons = set()
            relevant_ops = filter_operators_by_cluster(req, operators)
            for op in relevant_ops:
                feasible, reason = is_feasible(op, req, shift_end, debug=True)
                if not feasible and reason is not None:
                    reasons.add(reason)
            # Se la ragione è "arrival", incrementa arrival_fail; altrimenti se "work", incrementa work_fail.
            if "arrival" in reasons:
                stats['arrival_fail'] += 1
            elif "work" in reasons:
                stats['work_fail'] += 1
            # Se non è possibile determinarla, non si aggiornano ulteriori contatori

    return schedule, stats


# funzione per filtrare gli operatori per cluster
def filter_operators_by_cluster(request: Request, operators: List[Operator]) -> List[Operator]:
    """
    Filtra gli operatori per considerare solo quelli che appartengono al medesimo cluster
    della richiesta. Se nessun operatore ha il cluster_id corrispondente, restituisce
    tutti gli operatori.
    """
    filtered_ops = [op for op in operators if op.cluster_id == request.cluster_id]
    return filtered_ops if filtered_ops else operators
