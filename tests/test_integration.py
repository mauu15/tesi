import sys
import os
import random
import numpy as np
from sklearn.datasets import make_blobs

scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_path)

from operators_requests import Node, Operator, Request
from grs import grs_time, compute_travel_time
from mip_clustering import MIPClustering

def simple_requests(nodes, cluster_labels, durations):
    """
    Genera richieste con finestra temporale fissa (420, 780) per ciascun nodo.
    """
    requests = []
    fixed_window = (420, 780) # Finestra temporale fissa per tutte le richieste (7:00 - 13:00)
    for i, node in enumerate(nodes):
        dur = durations[i % len(durations)]
        req = Request(i=i, patient=node, duration=dur, temporal_window=fixed_window, cluster_id=cluster_labels[i])
        requests.append(req)
    return requests

def random_requests(nodes, cluster_labels, durations, alpha_min=420, alpha_max=450, beta_min_offset=40, beta_max=780):
    """
    Genera richieste con finestra temporale casuale.
    - alpha viene scelto casualmente tra alpha_min e alpha_max.
    - beta viene scelto casualmente tra (alpha + beta_min_offset) e beta_max.
    """
    requests = []
    for i, node in enumerate(nodes):
        alpha = random.randint(alpha_min, alpha_max)
        beta = random.randint(alpha + beta_min_offset, beta_max)
        dur = durations[i % len(durations)]
        req = Request(i=i, patient=node, duration=dur, temporal_window=(alpha, beta), cluster_id=cluster_labels[i])
        requests.append(req)
    return requests

def test_integration(use_random=True, is_morning=True):
    # 1. Genera un dataset con make_blobs
    n_samples = 40
    n_centers = 1
    points, _ = make_blobs(n_samples=n_samples, centers=n_centers, n_features=2, random_state=42)
    
    # 2. Esegue il clustering con il modello K-Medoids
    clustering_model = MIPClustering(points, K=n_centers)
    clustering_model.create_kmedoids_model()
    clustering_model.model.optimize()
    cluster_labels = clustering_model.get_cluster_labels()

    cluster_labels, medoid_mapping = MIPClustering.remap_cluster_labels(cluster_labels)

    # 3. Crea gli oggetti Node
    nodes = [Node(id=i, coordinates=(points[i, 0], points[i, 1])) for i in range(n_samples)]
    
    # Durate variabili per le richieste
    durations = [20, 25, 30]
    
    # 4. Genera le richieste: scegli tra simple_requests e random_requests
    """
    Dal main può essere scelta una delle due implementazioni:
    - simple_requests: finestra temporale fissa per ogni richiesta
    - random_requests: finestra temporale casuale per ogni richiesta (con parametri che
                        possono essere modificati)
    """

    """
    Alcuni orari noti:
    - 420: 7am       450: 7:30am
    - 480: 8am       510: 8:30am
    - 540: 9am       570: 9:30am
    - 600: 10am      630: 10:30am
    - 660: 11am      690: 11:30am
    - 720: 12pm      750: 12:30pm
    - 780: 1pm       
    """
    if use_random:
        requests = random_requests(nodes, cluster_labels, durations,
                                   alpha_min=420, alpha_max=450,
                                   beta_min_offset=40, beta_max=780)
    else:
        requests = simple_requests(nodes, cluster_labels, durations)
    
    # 5. Crea operatori: per ogni cluster unico usiamo il primo punto trovato come medoid
    operators = []
    assigned_clusters = {}
    for i, label in enumerate(cluster_labels):
        if label not in assigned_clusters:
            assigned_clusters[label] = i  # Usa il primo punto che compare per quel cluster
    for cluster, medoid_index in assigned_clusters.items():
        op = Operator(id=cluster, home=nodes[medoid_index], cluster_id=cluster)
        operators.append(op)

    print("-------------------------------------------------------------")
    print(f"TEST CON {n_samples} PAZIENTI E {len(assigned_clusters)} OPERATORI")
    print("-------------------------------------------------------------\n")
    
    # 6. Esegui il GRS - Time, passando il parametro is_morning per scegliere il turno
    schedule, stats = grs_time(operators, requests, is_morning)
    
    # 7. Visualizza i risultati
    print("\nRISULTATO SCHEDULING:")
    for op_id, req_list in schedule.items():
        print(f"Operatore {op_id} (Cluster: {op_id}):")
        for req in req_list:
            print(f"  Richiesta {req.i}: durata {req.duration}, finestra {req.temporal_window}, Cluster: {req.cluster_id}")

    # 8. Visualizza le statistiche
    print("\nSTATISTICHE:")
    total_requests = stats['total_requests']
    assigned = stats['assigned']
    not_assigned = stats['not_assigned']
    arrival_fail = stats['arrival_fail']
    work_fail = stats['work_fail']
    
    print(f"Richieste totali: {total_requests}")
    print(f"Richieste assegnate: {assigned} ({assigned/total_requests*100:.2f}%)")
    print(f"Richieste non assegnate: {not_assigned} ({not_assigned/total_requests*100:.2f}%)")
    print(f" - Non assegnate per arrival time non rispettato: {arrival_fail} ({arrival_fail/total_requests*100:.2f}%)")
    print(f" - Non assegnate per work time non rispettato: {work_fail} ({work_fail/total_requests*100:.2f}%)")

    
if __name__ == "__main__":
    # Imposta:
    # - use_random: True per usare random_requests, False per simple_requests.
    # - is_morning: True per turno mattutino, False per turno pomeridiano.
    use_random = True
    is_morning = True  # Modifica a False per simulare il turno pomeridiano
    test_integration(use_random, is_morning)
