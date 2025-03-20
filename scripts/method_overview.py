from typing import List, Dict, Any
import numpy as np
import copy

from grs_variants import grs_variants
from mip_clustering import MIPClustering
from data_loader import operators, requests, patients
from MOST import MOST
from visualization import plot_clusters
from utils import *

import matplotlib.pyplot as plt


def method_overview(
    requests,
    operators,
    patients,
    tau
):
    """
    Implementazione dell'Algoritmo 6: METHOD OVERVIEW
    che itera su Kmax configurazioni e seleziona la migliore
    per scheduling e routing delle richieste su più giorni/sessions.

    :param requests: Lista di richieste, ognuna con campi come:
              'id', 'project_id', 'day', 'duration', 'min_time_begin', 'max_time_begin'
    :param operators: Lista di operatori
    :param patients: Lista di pazienti
    :param morning_start, morning_end: Inizio/fine sessione mattutina (minuti)
    :param afternoon_start, afternoon_end: Inizio/fine sessione pomeridiana (minuti)
    :param epsilon: Peso per combinare SingleShiftRo(SSRo) e DoubleShiftRo(DSRo) 
    :param Kmax: Numero massimo di cluster da testare (default 20)

    :return: Un dizionario/struttura che contiene i risultati finali,
             inclusi costi, assegnazioni e qualunque output desideri.
    """

    # Parametri di default
    morning_start: int = 420  # 7:00
    morning_end:   int = 750  # 12:30 with 30 min ov
    afternoon_start: int = 960   # 16:00
    afternoon_end:   int = 1320  # 22:00 with 30 min ov
    
    epsilon: float = 0.4     # lambda per il peso tra SSRo e DSRo
    Kmax: int = 36         # Numero max di cluster da testare (1..Kmax)


    # Inizializzazione di eventuali strutture di costo globale
    total_cost = 0

    for op in operators:
        op["wo"] = 0 # wo
        op["single_shift_requests"] = 0 # SSRo
        op["double_shift_requests"] = 0 # DSRo
        op["worked_morning"] = False # indica se l'op ha lavorato al mattino
        op["worked_after_11:30am"] = False # indica se l'op ha lavorato dopo le 11:30
        op["morning_requests"] = []
        op["afternoon_requests"] = []
        op["d_o"] = 0 # tempo totale di attesa tra una richiesta e l'altra per l'operatore, settimanale
        op["road_time"] = 0 # tempo totale di spostamento per l'operatore, settimanale
        op["Lo"] = []


    session_bounds = {
        'm': (morning_start, morning_end),
        'a': (afternoon_start, afternoon_end),
    }

    sessions = ['m', 'a']

    # Memorizzo i costi di ciascun giorno/session
    cost_ds = {}

    # =======================================================================
    # Loop su tutti i giorni e su tutte le sessioni (morning, afternoon)
    # =======================================================================
    all_assignments = {}

    for d_i in range(7):
        print(f"[DEBUG] Inizio elaborazione giorno {d_i}")

        #Reset each operator variable related to his shift
        for op in operators:
            op["worked_morning"] = False
            op["worked_after_11:30am"] = False
            op["single_shift_requests"] = 0
            op["double_shift_requests"] = 0

        for s in sessions:
            print(f"[DEBUG] Elaborazione sessione: {s} per giorno {d_i}")
            update_operator_shift_counts(operators)
            update_operator_priority(operators, epsilon)

            # Estrazione della subset di richieste Rds per il giorno d_i e la sessione s
            day_requests = [r for r in requests if r["day"] == d_i]
            
            # Estrazione della subset di richieste Rds per il giorno d_i e la sessione s
            session_start, session_end = session_bounds[s]
            Rds = [
                r for r in day_requests
                if session_start <= parse_time_to_minutes(r["min_time_begin"]) < session_end]
            print(f"[DEBUG] Giorno {d_i} sessione {s}: {len(Rds)} richieste filtrate")
            
            # Estrazione della subset di pazienti Pds effettivamente coinvolti (cioè
            # quei pazienti che hanno almeno una richiesta in Rds)
            Pds = [p for p in patients if p['id'] in set(r['project_id'] for r in Rds)]
            
            
            # wpds = (numero di richieste per paziente p) / (totale richieste)
            wpds = {}
            for p_ in Pds:
                p_id = p_['id']
                
                p_requests = sum(1 for r_ in Rds if r_['project_id'] == p_id)
                wpds[p_id] = p_requests / len(Rds)
                # print(f"[DEBUG] Paziente {p_id} ha peso {wpds[p_id]:.2f}")
                

            
            points = np.array([[p['lat'], p['lon']] for p in Pds])
            
            # plot_clusters(
            #     points,
            #     clusters=clusters_dict,         
            #     medoid_indices=medoids_list,    
            #     filename=None,
            #     output_dir=None
            # )

            # ============================================================
            # Provo tutti i possibili K = 1..Kmax (20) e valuto il costo
            # ============================================================
            best_cost_for_k = None
            best_k = None
            best_clusters = None
            best_assignment = None

            w = wpds  # pesi per la funzione obiettivo

            
            # Prima di iterare sui vari k, mi salvo le variabili ho, eo, Lo, po, do, wo
            # per ogni operatore, in modo da poterle ripristinare dopo aver assegnato
            # gli operatori ai cluster.

            for op in operators:
                op["Lo_k"] = {}
                op["current_patient_id_k"] = {}
                op["do_k"] = {}
                op["wo_k"] = {}
                op["road_time_k"] = {}
                op["worked_morning_k"] = {}
                op["worked_after_11:30am_k"] = {}


           
            print(f"[DEBUG] Inizio test per diversi valori di K (1..{Kmax}) per giorno {d_i} sessione {s}")

            for k in range(1, Kmax):
                print(f"[DEBUG] Test con k = {k}")
                 # Setto lo stato degli operatori in base alla sessione, mattina o pomeriggio
                # e aggiorno i contatori di shift e priorità
                if s == 'm':
                    for op in operators:
                        set_operator_state_morning(op)
                else:
                    for op in operators:
                        set_operator_state_afternoon(op)

                # PUNTO CRITICO, controllare la copy e l'assegnazione
                # Salva lo stato in tabelle temporanee per il valore k corrente
                for op in operators:
                    # print(f"[DEBUG] Prima del backup per k={k} - Operatore {op['id']}: global_assignments = {op['global_assignments']}")
                    op["current_patient_id_k"][k] = op["current_patient_id"]
                    op["wo_k"][k] = op["wo"]
                    op["road_time_k"][k] = 0
                    op["Lo_k"][k] = []
                    op["do_k"][k] = 0
                    
                     #Check operator params corecteness
                    #print("Operator ", op["id"], " - global_assignments: ", op["global_assignments"], " - Lo: ", op["Lo"], " - Lok: ", op["Lo_k"][k], " h_o: ", op["ho"], " hok: ", op["ho_k"][k], " e_o: ", op["eo"], " eok: ", op["eo_k"][k], " dok: ", op["do_k"][k], " w_o: ", op["wo"], " wok: ", op["wo_k"][k]) 


                P_indices = list(range(len(Pds))) # indici dei pazienti

                # Costruzione del dizionario tau_indices: le chiavi sono coppie di indici (i, j)
                tau_indices = {}
                for i in range(len(Pds)):
                    for j in range(len(Pds)):
                        id_i = Pds[i]['id']
                        id_j = Pds[j]['id']
                        tau_indices[(i, j)] = tau.get((id_i, id_j), float('inf'))

                # Costruzione del dizionario dei pesi indicizzati: le chiavi sono gli indici di Pds
                w_indices = {}
                for i in range(len(Pds)):
                    p_id = Pds[i]['id']
                    w_indices[i] = wpds[p_id]

                clusterer = MIPClustering(
                    P = P_indices,       # lista degli indici dei pazienti
                    K = k,         # numero di cluster
                    tau = tau_indices,     # la matrice delle distanze
                    w = w_indices          # i pesi per paziente { i: wpds[i] }
                )

                grb_status = clusterer.solve(time_limit=100)

                if grb_status is False:
                    print(f"[DEBUG] Clustering con k={k} non ammissibile.")
                    input("Press Enter to continue...")
                    continue


                clusters_dict = clusterer.get_clusters()
                medoids_list = clusterer.get_medoids()

                from visualization import plot_clusters


                #plot_clusters(np.array([[p['lat'], p['lon']] for p in Pds]), clusters_dict, medoids_list)

                print(f"[DEBUG] Clustering con k={k} completato, {len(clusters_dict)} cluster creati.")

                clusters = {}
                for cluster_id, point_indices in clusters_dict.items():
                    cluster_patient_ids = [Pds[idx]['id'] for idx in point_indices]
                    clusters[cluster_id] = [Pds[idx] for idx in point_indices]

            
                # ------------------------------------------------------------
                # 2) Calcolo di µc per ogni cluster
                # ------------------------------------------------------------

                cluster_info = []
                total_mu = 0
                
                session_start, session_end = session_bounds[s]

                for c_idx, cluster in clusters.items():
                    cluster_patients_ids = {p["id"] for p in cluster}
                    Rdsc = [req for req in Rds if req['project_id'] in cluster_patients_ids]

                    # calcolo mc
                    mc = 0
                    if len(Rdsc) > 0:
                        mc = MOST(Rdsc, session_start, session_end)
                    
                    # somma durate di Rdsc
                    sum_durations = sum(rq['duration'] for rq in Rdsc)
                    five_hours_in_minutes = 300
                    mu_c = max(np.ceil(sum_durations / five_hours_in_minutes), mc)
                    total_mu += mu_c

                    cluster_info.append({
                        'cluster_idx': c_idx,
                        'Rdsc': Rdsc,
                        'mc': mc,
                        'mu_c': mu_c
                    })

                # µk = ∑c∈C µc
                mu_k = total_mu

                # ------------------------------------------------------------
                # 3) Selezione e sorting operatori Ods
                # ------------------------------------------------------------
                
                
                # Ordiniamo O in base a op['priority']
                O_sorted = sorted(operators, key=lambda x: x['priority'])

                # Calcoliamo il numero di operatori necessari
                import math
                num_ops_needed = int(mu_k)
                # print(mu_k, len(O_sorted))
                # input("Press Enter to continue...")
                Ods = O_sorted[:num_ops_needed]

                cluster_ops = {}
                start_index = 0
                for info in cluster_info:

                    #Get the mu_c operators from Ods closet to the cluster c
                    #for each medoid in the cluster, compute tau[op_id, medoid_id] and sort the operators by this distance
                    #take the first mu_c operators

                    c_idx = info['cluster_idx'] # cluster index in clusters dict
                    needed_for_c = info['mu_c']

                    # 1) Ottiengo l'ID del medoid corrispondente a questo cluster
                    medoid_id = medoids_list[c_idx]

                     # 2) Calcola la distanza di ogni operatore dal medoid e ordina
                     #Shift of 249 in the distance matrix to get the correct index of the operator
                    for op in Ods:
                        op_id = op["id"]
                        op["dist_to_medoid"] = tau[op_id + 249 , medoid_id]

                    # 3) Ordino gli operatori per distanza crescente
                    Ods_sorted_by_dist = sorted(Ods, key=lambda x: x["dist_to_medoid"])

                    # 4) Prendo i primi needed_for_c operatori
                    assigned_ops = Ods_sorted_by_dist[:int(needed_for_c)]


                    # 5) Rimuovo gli operatori assegnati da Ods (per non assegnarli a un altro cluster)
                    for op_assigned in assigned_ops:
                        Ods.remove(op_assigned)

                    cluster_ops[c_idx] = assigned_ops

                    
                # ------------------------------------------------------------
                # 5) Chiamata a grs_variants(...) su ciascun cluster
                # ------------------------------------------------------------
                
                cost_k = 0
                d_ok = 0
                for info in cluster_info:
                    c_idx = info['cluster_idx']
                    assigned_ops = cluster_ops[c_idx]
                    
                    print("Solving GRS for cluster ", c_idx)
                    print(""*5)

                    rc, ovc, doc = grs_variants(
                        operators=assigned_ops,               # operatori per il cluster
                        requests=info['Rdsc'],                # richieste di quel cluster
                        patients=clusters[c_idx],             # lista dei pazienti del cluster
                        shift_end=session_bounds[s][1],       # orario di fine turno in base alla sessione, [1] serve a selezionare la fine
                        down_time_true=False,                 # o True, a seconda della logica
                        tau=tau, k=k                            # matrice delle distanze
                    )
                    

                    #Check operator params correcteness
                    # for op in assigned_ops:
                    #     print("Operator ", op["id"], " -  Lo: ", op["Lo"], " - Lok: ", [op["Lo_k"][k], " h_o: ", op["ho"], " e_o: ", op["eo"], "d_o: ", op["do"], " dok: ", op["do_k"][k], " w_o: ", op["wo"], " wok: ", op["wo_k"][k], "road_k: ", op["road_time_k"][k]) 


                    
                    cost_k += (rc + ovc)
                    d_ok += doc

                # Fine loop su c => otteniamo cost_k come la somma
                # Salviamo cost_k se è il migliore
                if best_cost_for_k is None or cost_k < best_cost_for_k:
                    best_cost_for_k = cost_k
                    best_k = k
                    best_clusters = clusters
                    
                    best_assignment = {
                        'cluster_ops': cluster_ops,
                        'clusters_info': cluster_info
                    }
                    print(f"[DEBUG] Nuovo best_cost trovato: {best_cost_for_k} con k = {best_k} totale down time: {d_ok} totale operatori: ", mu_k)

            # -----------------------------------------------------------------------------
            # Fine loop su k in [1, Kmax]:
            #   - best_cost_for_k: costo minimo ottenuto tra tutte le configurazioni
            #   - best_k: è il numero di cluster (k) che ha generato il costo minimo
            #   - best_assignment: contiene i dettagli dell'assegnazione migliore (i cluster e i relativi operatori)
            #
            # Ora aggiornamo lo stato finale di ciascun operatore in base alla configurazione ottimale
            # (quella salvata in best_assignment). Durante le iterazioni, per ogni operatore abbiamo salvato,
            # in tabelle temporanee (op["ho_k"], op["eo_k"], op["Lo_k"], op["po_k"], op["do_k"], op["wo_k"]),
            # i valori calcolati per ciascun possibile valore di k. best_k rappresenta l'indice della configurazione
            # ottimale.
            #
            # Questo blocco di codice itera su ciascun cluster (c_idx) e, per ogni operatore assegnato a quel
            # cluster, ripristina i seguenti campi:
            #   - "ho": il tempo residuo nel turno dell'operatore (ho[k] per k = best_k)
            #   - "eo": l'orario di fine turno (eo[k] per k = best_k)
            #   - "Lo": la lista delle richieste assegnate (viene effettuato un deepcopy da Lo[k])
            #   - "po": un parametro (ad es. un output intermedio) calcolato per la configurazione k migliore
            #   - "do": il tempo di attesa accumulato, come calcolato per best_k
            #   - "wo": il costo totale o tempo di lavoro accumulato per l'operatore
            #
            # Consolidiamo quindi i risultati ottenuti dalla configurazione migliore,
            # aggiornando definitivamente lo stato degli operatori sulla base della configurazione che ha
            # minimizzato il costo per la giornata/sessione corrente.
            # -----------------------------------------------------------------------------
            
            if best_assignment is not None:
                print(f"[DEBUG] Consolidamento dello stato per giorno {d_i} sessione {s} con best_k = {best_k}")
                for c_idx, assigned_ops in best_assignment['cluster_ops'].items():
                    # salvo i campi finali di interesse per ogni operatore
                    for op in assigned_ops:
                        op["Lo"] = op["Lo"] + op["Lo_k"][best_k]
                        op["do"] += op["do_k"][best_k]
                        op["wo"] = op["wo_k"][best_k]
                        if best_k in op["worked_after_11:30am_k"].keys():
                            op["worked_after_11:30am"] = op["worked_after_11:30am_k"][best_k]
                        op["road_time"] += op["road_time_k"][best_k]
                        # print(f"[DEBUG] Dopo consolidamento - Operatore {op['id']}: global_assignments = {op['global_assignments']}")


            # Salviamo cost_ds[(d_i, s)] = best_cost_for_k
            cost_ds[(d_i, s)] = best_cost_for_k if best_cost_for_k is not None else 0
            print(""*5)
            print(f"[DEBUG] Giorno {d_i} sessione {s}: costo = {cost_ds[(d_i, s)]}")
            print(""*5)
            input()
             # Genera DataFrame per le statistiche globali e per le assegnazioni

            # print("[DEBUG] Stato degli operatori prima del report:")
            # for op in operators:
                # print(f"Operatore {op['id']} - global_assignments: {op['global_assignments']}, Lo: {op.get('Lo')}")
            global_stats_df = display_global_statistics(operators)
            assignments_df = display_assignments_with_shifts(operators)
            #save_statistics("TradeOff", d_i, s, best_k, cost_ds, best_cost_for_k, global_stats_df, assignments_df)
            all_assignments[(d_i, s)] = best_assignment


    # Calcolo del costo totale
    total_cost = sum(cost_ds.values())

    
    # create_directed_graph_of_schedule(...)

    print("[METHOD OVERVIEW] - Completed.")
    print(f"Total cost over all days/sessions: {total_cost}")

    # Ritorna i risultati finali
    return {
        'cost_ds': cost_ds,
        'total_cost': total_cost,
        'details': None 
    }


def main():
    
    tau = {}
    json_path = "../mapping/distance_matrix_pane_rose.json"
    with open(json_path, "r") as f:
        tau = eval(f.read())
    
    # print("tau =", tau, type(tau))
    
    results = method_overview(requests, operators, patients, tau)
    print(results)

    pass

if __name__ == "__main__":
    main()


