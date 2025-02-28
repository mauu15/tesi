import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from operators_requests import Node, Operator, Request
from grs import grs, compute_travel_time 

#generato con GPT

def test_grs():
    # Creiamo alcuni nodi
    depot = Node(id=0, coordinates=(0.0, 0.0))
    node1 = Node(id=1, coordinates=(3.0, 4.0))   # Distanza ~5 da depot
    node2 = Node(id=2, coordinates=(6.0, 8.0))   # Distanza ~10
    node3 = Node(id=3, coordinates=(1.0, 1.0))   # Distanza ~1.41
    node4 = Node(id=4, coordinates=(2.0, 2.0))   # Distanza ~2.83

    # Creiamo operatori; assegnamo cluster_id in base alla loro area di operatività
    op1 = Operator(id=1, home=depot, cluster_id=0)  # Operatore per il cluster 0
    op2 = Operator(id=2, home=depot, cluster_id=1)  # Operatore per il cluster 1
    operators = [op1, op2]

    # Creiamo richieste, ciascuna con un cluster_id assegnato dal clustering
    # Richieste appartenenti al cluster 0
    req1 = Request(i=1, patient=node1, duration=20, temporal_window=(420, 500), cluster_id=0)
    req3 = Request(i=3, patient=node3, duration=15, temporal_window=(420, 480), cluster_id=0)
    # Richieste appartenenti al cluster 1
    req2 = Request(i=2, patient=node2, duration=25, temporal_window=(430, 510), cluster_id=1)
    req4 = Request(i=4, patient=node4, duration=10, temporal_window=(420, 490), cluster_id=1)
    requests = [req1, req2, req3, req4]

    # Eseguiamo il GRS (la funzione grs dovrebbe utilizzare internamente il filtro dinamico per cluster)
    schedule = grs(operators, requests)

    # Stampiamo lo schedule risultante
    print("\nRISULTATO SCHEDULING:")
    for op_id, req_list in schedule.items():
        print(f"Operatore {op_id}:")
        for req in req_list:
            print(f"  Richiesta {req.i} (Cluster: {req.cluster_id})")

    
if __name__ == "__main__":
    test_grs()
