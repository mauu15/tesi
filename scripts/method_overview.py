from typing import List, Dict, Any
import numpy as np
import copy

from grs_variants import grs_variants
from mip_clustering import MIPClustering
from data_loader import operators, requests, patients
from MOST import MOST
from visualization import plot_clusters
from utils import *
from copy import deepcopy
from combine_results import combine_results
#from scheduling_mapper import create_hhc_map_session, create_map_from_txt_schedules


import matplotlib.pyplot as plt


def method_overview(
    requests,
    operators,
    patients,
    tau,
    variant,
    epsilon: float, 
    down_time_true: bool,
    Kmax: int,
    multiplier: float,
    kfixed: int = None,
):
    """
    Implementazione dell'Algoritmo METHOD OVERVIEW

    L'algoritmo si occupa di elaborare lo scheduling e il routing delle richieste su
    più giorni e sessioni (mattina e pomeriggio), selezionando la configurazione con il
    costo globale minore. Per ogni giorno della settimana e per ciascuna sessione, il metodo:

      1. Filtra le richieste in base all'orario della sessione e identifica i pazienti effettivamente interessati.
      2. Calcola i pesi per ciascun paziente in funzione del numero di richieste a lui associate.
      3. Esegue il clustering dei pazienti utilizzando la matrice delle distanze (tau) e testando
         diverse configurazioni: se non viene specificato un valore fisso di k (kfixed), si iterano
         tutti i valori da 1 a (Kmax-1), altrimenti viene usato soltanto il valore di kfixed.
      4. Per ogni configurazione di cluster viene applicato il modello MIPClustering per ottenere:
             - I cluster e i medoids corrispondenti.
      5. Calcola, per ciascun cluster, il parametro µc, ovvero il numero minimo di operatori necessari simultaneamente
      6. Si applica un fattore γ come “margine di sicurezza” sul numero di operatori stimato, per verificare se la 
         disponibilità di operatori effettiva è sufficiente a coprire le richieste di tutti i cluster.
      7. Assegna gli operatori ai cluster in maniera greedy, ordinandoli in base alla distanza calcolata 
         tramite tau rispetto ai medoids.
      8. Contestualmente, vengono salvate variabili temporanee per ciascun operatore, in modo da poter 
         comparare e ripristinare lo stato a seconda della configurazione di k.
      9. Il costo totale della configurazione corrente viene calcolato sommando i costi di routing ed 
         overtime, con eventuali penalizzazioni per richieste non assegnate.
     10. Infine, viene selezionata la configurazione con il costo minimo tra quelle ammissibili.

    I risultati includono:
      - I costi globali e per sessione (routing, overtime, penalità per richieste non assegnate).
      - Le assegnazioni finali degli operatori e la configurazione (valore di k) ottimale scelta.
      - La memorizzazione dei file di scheduling per ciascun operatore e l'output grafico (cluster plot).

    I parametri in ingresso sono:
      - requests: lista di richieste con campi come 'id', 'project_id', 'day', 'duration', 'min_time_begin', 'max_time_begin'.
      - operators: lista di operatori, che vengono aggiornati durante le diverse iterazioni.
      - patients: lista dei pazienti.
      - tau: matrice (o dizionario) delle distanze, usata per conoscere i tempi di percorrenza.
      - variant: nome della configurazione corrente (tipicamente una lettera, es. "A").
      - epsilon: peso per combinare differenti componenti di costo (es. SingleShiftRo e DoubleShiftRo).
      - down_time_true: flag per il calcolo dei costi in base al down time.
      - Kmax: numero massimo di cluster da testare (in assenza di un k fisso, si itera da 1 fino a Kmax-1).
      - multiplier: fattore usato per determinare il numero di operatori necessari.
      - kfixed: se specificato, viene utilizzato esclusivamente questo valore di k, ignorando l'intervallo.

    L’algoritmo restituisce una struttura contenente i costi complessivi per giorno e sessione, 
    insieme a dettagliamenti relativi alle assegnazioni e ai costi specifici, utile per il reporting e 
    l’analisi comparativa delle configurazioni.
    """

    # Parametri di configurazione
    morning_start: int = 420  # 7:00
    morning_end:   int = 750  # 12:30 with 30 min ov
    afternoon_start: int = 960   # 16:00
    afternoon_end:   int = 1320  # 22:00 with 30 min ov
    
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
    total_overtime_cost = 0
    total_routing_cost = 0

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
            update_operator_priority(operators, epsilon, d_i, s)

            
            for op in operators:
                print("SSRo: ", np.round(op["SSRo"], 2), " - DSRo: ", np.round(op["DSRo"], 2), "operatore: ", op["id"], "priority: ", op["priority"])

            # Ordiniamo O in base a op['priority']
            O_sorted = sorted(operators, key=lambda x: x['priority'])
            print([op["id"] for op in O_sorted])
            input()

            # Estrazione della subset di richieste Rds per il giorno d_i e la sessione s
            day_requests = [r for r in requests if r["day"] == d_i]
            
            # Estrazione della subset di richieste Rds per il giorno d_i e la sessione s
            session_start, session_end = session_bounds[s]
            Rds = [
                r for r in day_requests
                if session_start <= parse_time_to_minutes(r["min_time_begin"]) < session_end]
            print(f"[DEBUG] Giorno {d_i} sessione {s}: {len(Rds)} richieste filtrate")

            baseline_operators = deepcopy(operators)
            
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
                op["overtime_minutes_k"] = {}

          
            print(f"[DEBUG] Inizio test per diversi valori di K (1..{Kmax}) per giorno {d_i} sessione {s}")
            
            
            unassigned_requests_k = {}
            k_values = range(1, Kmax) if kfixed is None else [kfixed]
            for k in k_values:
                unassigned_requests_k[k] = False
                cost_k = 0
                routing_cost = 0
                overtime_cost = 0
                d_ok = 0
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
                    op["Lo_k"][k] = deepcopy(op["Lo"])
                    op["do_k"][k] = 0
                    op["overtime_minutes_k"][k] = 0
                    
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
                    # input("Press Enter to continue...")
                    continue


                clusters_dict = clusterer.get_clusters()
                medoids_list = clusterer.get_medoids()

                from visualization import plot_clusters


                #plot_clusters(np.array([[p['lat'], p['lon']] for p in Pds]), clusters_dict, k, variant, medoids_list, output_dir=RESULTS_DIR)

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
                    exp_op = np.ceil(sum_durations / five_hours_in_minutes)
                    mu_c = max(exp_op, mc)
                    total_mu += mu_c

                    print("Min same time: ", mc, " - Stima con somma tempi richieste: ", exp_op, " - Numero richieste: ", len(Rdsc))
                
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
                
                
              

                # Calcoliamo il numero di operatori necessari
                import math
                num_ops_needed = int(np.ceil(mu_k * multiplier))
               



                print("------------------------------------------------------------")
                print(f"Operatori assegnati per configurazione {k} con fattore moltiplicativo: {multiplier}", num_ops_needed)
                print("------------------------------------------------------------")
                

                if num_ops_needed > len(operators):
                    print(f"[DEBUG] Attenzione: numero di operatori necessari ({num_ops_needed}) maggiore del totale ({len(operators)})")
                    print(f"[DEBUG] Salto la configurazione con k = {k}")
                    cost_k = float('inf')
                    continue


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
                    needed_for_c = int(np.round(info['mu_c']*multiplier, 0))

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
                    print("---------------")
                    print(f"NUmber of assigned operators in cluster {c_idx} of configuration {k}: ", len(assigned_ops))
                    print("---------------")

                    # 5) Rimuovo gli operatori assegnati da Ods (per non assegnarli a un altro cluster)
                    for op_assigned in assigned_ops:
                        Ods.remove(op_assigned)

                    cluster_ops[c_idx] = assigned_ops

                    
                # ------------------------------------------------------------
                # 5) Chiamata a grs_variants(...) su ciascun cluster
                # ------------------------------------------------------------
                
                
                for info in cluster_info:
                    c_idx = info['cluster_idx']
                    assigned_ops = cluster_ops[c_idx]
                    
                    print("Solving GRS for cluster ", c_idx)
                    print(""*5)

                    rc, ovc, doc, n_used_ops = grs_variants(
                        operators=assigned_ops,               # operatori per il cluster
                        requests=info['Rdsc'],                # richieste di quel cluster
                        patients=clusters[c_idx],             # lista dei pazienti del cluster
                        shift_end=session_bounds[s][1],       # orario di fine turno in base alla sessione, [1] serve a selezionare la fine
                        down_time_true=down_time_true,                 # o True, a seconda della logica
                        tau=tau, k=k                            # matrice delle distanze
                    )
                    


                    #Check operator params correcteness
                    if len(n_used_ops) > 0:
                        print("Operatori non utilizzati: ", n_used_ops)
                   
                    
                    # print("Lo_k per cluster ", c_idx, ": ")
                    # for op in assigned_ops:
                    #     for r in op["Lo_k"][k]:
                    #         print(r[0]["id"])

                    
                    

                    cost_k += (rc + ovc)
                    routing_cost += rc
                    overtime_cost += ovc
                    d_ok += doc
                

                #Controlla se tuttte le richieste sono state assegnate altrimenti le penalizza

                assigned_requests = []
                for op in operators:
                    for r in op["Lo_k"][k]:
                        assigned_requests.append(r[0])

                unassigned_requests = [r for r in Rds if r["id"] not in [r_["id"] for r_ in assigned_requests]]

                print(len(unassigned_requests), " richieste non assegnate nella configurazione ", k)
                print(len(assigned_requests), " richieste assegnate nella configurazione ", k)

                if len(unassigned_requests) > 0:
                    print("Richieste non assegnate: ", unassigned_requests, "config k = ", k)
                    unassigned_requests_k[k] = True

                for r in unassigned_requests:
                    # penalizza il costo

                    cost_k += r["duration"]


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
                   
                    overtime_cost_session = overtime_cost
                    routing_cost_session = routing_cost
                    print(f"[DEBUG] Nuovo best_cost trovato: {best_cost_for_k} con k = {best_k} totale down time: {d_ok} totale operatori: ", mu_k)
                  

            if best_assignment is not None:

                print(f"[DEBUG] Consolidamento dello stato per giorno {d_i} sessione {s} con best_k = {best_k}")
                #Verifica se in tutte le configurazioni di k ci sono richieste non assegnate
                #Può preferire pagare il costo di non prendere una richiesta a volte
                if all(unassigned_requests_k.values()):
                    print(f"[DEBUG] Tutte le configurazioni di k hanno richieste non assegnate per giorno {d_i} sessione {s}.")

                    
                    input()

                for c_idx, assigned_ops in best_assignment['cluster_ops'].items():
                    # salvo i campi finali di interesse per ogni operatore
                    for op in assigned_ops:
                        op["Lo"] = op["Lo_k"][best_k]
                        op["do"] += op["do_k"][best_k]
                        op["wo"] = op["wo_k"][best_k]
                        if best_k in op["worked_after_11:30am_k"].keys():
                            op["worked_after_11:30am"] = op["worked_after_11:30am_k"][best_k]
                        op["road_time"] += op["road_time_k"][best_k]
                        op["overtime_minutes"] = op["overtime_minutes_k"][best_k]
                        # print(f"[DEBUG] Dopo consolidamento - Operatore {op['id']}: global_assignments = {op['global_assignments']}")


            # Salviamo cost_ds[(d_i, s)] = best_cost_for_k
            cost_ds[(d_i, s)] = best_cost_for_k if best_cost_for_k is not None else 0
            print(""*5)
            print(f"[DEBUG] Giorno {d_i} sessione {s}: costo = {cost_ds[(d_i, s)]}")
            print(""*5)



            
            #save_operator_scheduling(operators, baseline_operators, tau, variant_name=variant, day=d_i, session=s, patients=patients)

            
            # Genera DataFrame per le statistiche globali e per le assegnazioni

            # print("[DEBUG] Stato degli operatori prima del report:")

            requests_map = {}
            for r in requests:
                req_id = r["id"]
                requests_map[req_id] = r

            # patient_id -> (lat, lon)
            patients_map = {}
            for p in patients:
                pid = p["id"]
                patients_map[pid] = (p["lat"], p["lon"])

            # create_map_from_txt_schedules(
            #     operators=operators,
            #     requests_map=requests_map,
            #     patients_map=patients_map,
            #     tau=tau,
            #     day=d_i,
            #     session=s,
            #     variant_name=variant,
            #     output_dir="results"
            # )

            # input()

            total_cost = sum(cost_ds.values())
            total_overtime_cost += overtime_cost_session
            total_routing_cost += routing_cost_session
            print("[DEBUG] - len(Rds): ", len(Rds), " - assigned requests: ", sum(len(op["Lo"]) for op in operators))
            
            session_stats_df = display_session_statistics(operators, baseline_operators, assigned_requests, unassigned_requests)
            session_deltas_df = display_session_deltas(operators, baseline_operators)
            #save_statistics(variant, d_i, s, best_k, cost_ds, total_cost=total_cost, global_stats_df=session_stats_df, assignments_df=session_deltas_df)
            all_assignments[(d_i, s)] = best_assignment
            


    
    # scheduling settimanale, da reimplementare
    #save_operator_scheduling(operators, baseline_operators, tau, variant_name=variant)

    print("[METHOD OVERVIEW] - Completed.")
    if kfixed is None:
        print(f"Parametri di configurazione: {variant}, lambda={epsilon}, down_time_true={down_time_true}, Kmax={Kmax}, multiplier={multiplier}\n")
    else:
        print(f"Parametri di configurazione: {variant}, lambda={epsilon}, down_time_true={down_time_true}, kfixed={kfixed}, multiplier={multiplier}\n")
        
    print(f"Total cost over all days/sessions: {total_cost}")
    print(f"Total overtime cost: {total_overtime_cost}")
    print(f"Total routing cost: {total_routing_cost}")
    print(f"Total overtime cost sum operators: {sum(max(op['wo'] - op['Ho'], 0) for op in operators)*0.29}")
    print(f"Average waiting time: {sum(op['do'] for op in operators) / len(operators)}")
    print(f"Average SSRo: {sum(op['SSRo'] for op in operators) / len(operators)}")
    print(f"Average DSRo: {sum(op['DSRo'] for op in operators) / len(operators)}")


    unserved_requests = [r for r in requests if r["id"] not in [rq[0]["id"] for op in operators for rq in op["Lo"]]]
    print(f"Unserved requests: {unserved_requests}")

    total_time_served = sum(sum(rq[0]["duration"] for rq in op["Lo"]) for op in operators)
    total_time = sum(rq["duration"] for rq in requests)

    print(f"Total time served ratio: {total_time_served*100 / total_time:.2f}")




    # Ritorna i risultati finali
    return {
        'cost_ds': cost_ds,
        'total_cost': total_cost,
        'total_overtime_cost': total_overtime_cost,
        'total_routing_cost': total_routing_cost,
        'details': None 
    }


import os
import sys
import itertools
import string
import pandas as pd

def run_all_configurations():
    """
    Esegue tutte le configurazioni possibili, salvando i risultati in cartelle separate.
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(current_dir, "../mapping/distance_matrix_pane_rose.json")
    with open(json_path, "r") as f:
        tau = eval(f.read())
    
    # PARAMETRI DI CONFIGURAZIONE FISSI
    Kmax = 37  # Numero max di cluster da testare (1..Kmax-1)
    kfixed = None  # Se specificato, usa questo valore fisso per k
    
    # Valori da testare per le 3 variabili
    epsilons = [0.5, 0.4, 0.6]         # 3 valori per epsilon
    down_time_trues = [True, False]     # 2 valori per down_time_true
    multipliers = [1.25, 1]            # 2 valori per multiplier
    
    configurazioni = list(itertools.product(epsilons, down_time_trues, multipliers))
    variant_letters = list(string.ascii_uppercase[:len(configurazioni)])  # ['A', 'B', ..., 'L']
    
    # Esegue il metodo per tutte le configurazioni e salva i risultati
    for letter, (epsilon, down_time_true, multiplier) in zip(variant_letters, configurazioni):
        variant_name = letter  # Usa la lettera come nome variante
        print(f"Processing variant {variant_name}: epsilon={epsilon}, down_time_true={down_time_true}, multiplier={multiplier}")
        
        results = method_overview(requests, operators, patients, tau,
                                  variant=variant_name,
                                  epsilon=epsilon,
                                  down_time_true=down_time_true,
                                  Kmax=Kmax,
                                  multiplier=multiplier,
                                  kfixed=kfixed)
        print(results)

        # Salva i parametri usati in un file nella cartella della variante
        variant_dir = os.path.join(RESULTS_DIR, f"variant_{variant_name}")
        os.makedirs(variant_dir, exist_ok=True)
        with open(os.path.join(variant_dir, "parameters.txt"), "w") as f:
            f.write(f"epsilon: {epsilon}\n")
            f.write(f"down_time_true: {down_time_true}\n")
            f.write(f"multiplier: {multiplier}\n")
    
        # Salva i risultati globali e le assegnazioni
        save_global_statistics(operators,
                               variant_name=variant_name,
                               total_cost=results['total_cost'],
                               total_overtime_cost=results['total_overtime_cost'],
                               total_routing_cost=results['total_routing_cost'],
                               requests=requests)
    
        save_global_assignments(operators, variant_name=variant_name)
    
        # Calcola e salva le statistiche per ciascun operatore
        calculate_and_save_stats(variant_name)
    
        # Legge il file degli assignments e genera i boxplot
        assignments_file = os.path.join(variant_dir, f"global_assignments_{variant_name}.csv")
        df_assign = pd.read_csv(assignments_file)
        plot_time_distributions(df_assign, variant_name, output_dir=RESULTS_DIR, show_plot=False)

        save_histograms(variant_name)

        
    combine_results()

def run_test_configuration():
    """
    Esegue una configurazione di test per verificare il funzionamento del metodo.
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(current_dir, "../mapping/distance_matrix_pane_rose.json")
    with open(json_path, "r") as f:
        tau = eval(f.read())
    
    Kmax = 3  # Numero max di cluster
    kfixed = 1  # Se specificato, usa questo valore fisso per k

    # Configurazione di test
    epsilon = 0.5
    down_time_true = True
    multiplier = 1.5
    variant_name = "A_fixed1"  # Nome della variante per il test

    print(f"Processing test variant {variant_name}: epsilon={epsilon}, down_time_true={down_time_true}, multiplier={multiplier}")
    
    results = method_overview(requests, operators, patients, tau,
                              variant=variant_name,
                              epsilon=epsilon,
                              down_time_true=down_time_true,
                              Kmax=Kmax,
                              multiplier=multiplier,
                              kfixed=kfixed)
    print(results)

    variant_dir = os.path.join(RESULTS_DIR, f"variant_{variant_name}")
    os.makedirs(variant_dir, exist_ok=True)
    with open(os.path.join(variant_dir, "parameters.txt"), "w") as f:
        f.write(f"epsilon: {epsilon}\n")
        f.write(f"down_time_true: {down_time_true}\n")
        f.write(f"multiplier: {multiplier}\n")

    save_global_statistics(operators,
                           variant_name=variant_name,
                           total_cost=results['total_cost'],
                           total_overtime_cost=results['total_overtime_cost'],
                           total_routing_cost=results['total_routing_cost'],
                           requests=requests)
    
    save_global_assignments(operators, variant_name=variant_name)
    
    # calculate_and_save_stats(variant_name)
    
    assignments_file = os.path.join(variant_dir, f"global_assignments_variant{variant_name}.csv")
    df_assign = pd.read_csv(assignments_file)
    plot_time_distributions(df_assign, variant_name, output_dir=RESULTS_DIR, show_plot=False)

    save_histograms(variant_name)

    

def run_specific_configuration(variant_letter):
    """
    Esegue la configurazione corrispondente alla lettera passata (es. "A", "B", ecc.)
    A = (0.5, True, 1.25)
    B = (0.5, True, 1)
    C = (0.5, False, 1.25)
    D = (0.5, False, 1)
    E = (0.4, True, 1.25)
    F = (0.4, True, 1)
    G = (0.4, False, 1.25)
    H = (0.4, False, 1)
    I = (0.6, True, 1.25)
    J = (0.6, True, 1)
    K = (0.6, False, 1.25)
    L = (0.6, False, 1)
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(current_dir, "../mapping/distance_matrix_pane_rose.json")
    with open(json_path, "r") as f:
        tau = eval(f.read())
    
    Kmax = 37  # Numero max di cluster
    kfixed = None  # Se specificato, usa questo valore fisso per k

    # Definisci i valori da testare
    epsilons = [0.5, 0.4, 0.6]
    down_time_trues = [True, False]
    multipliers = [1.25, 1] 

    configurazioni = list(itertools.product(epsilons, down_time_trues, multipliers))
    variant_letters = list(string.ascii_uppercase[:len(configurazioni)])

    if variant_letter.upper() not in variant_letters:
        print(f"Errore: Variante {variant_letter} non valida. Scegli una delle seguenti: {', '.join(variant_letters)}")
        return

    index = variant_letters.index(variant_letter.upper())
    epsilon, down_time_true, multiplier = configurazioni[index]
    variant_name = variant_letter.upper()

    print(f"Processing variant {variant_name}: epsilon={epsilon}, down_time_true={down_time_true}, multiplier={multiplier}")
    
    results = method_overview(requests, operators, patients, tau,
                              variant=variant_name,
                              epsilon=epsilon,
                              down_time_true=down_time_true,
                              Kmax=Kmax,
                              multiplier=multiplier,
                              kfixed=kfixed)
    print(results)

    variant_dir = os.path.join(RESULTS_DIR, f"variant_{variant_name}")
    os.makedirs(variant_dir, exist_ok=True)
    with open(os.path.join(variant_dir, "parameters.txt"), "w") as f:
        f.write(f"epsilon: {epsilon}\n")
        f.write(f"down_time_true: {down_time_true}\n")
        f.write(f"multiplier: {multiplier}\n")
    
    save_global_statistics(operators,
                           variant_name=variant_name,
                           total_cost=results['total_cost'],
                           total_overtime_cost=results['total_overtime_cost'],
                           total_routing_cost=results['total_routing_cost'],
                           requests=requests)
    
    save_global_assignments(operators, variant_name=variant_name)
    
    calculate_and_save_stats(variant_name)
    
    assignments_file = os.path.join(variant_dir, f"global_assignments_{variant_name}.csv")
    df_assign = pd.read_csv(assignments_file)
    plot_time_distributions(df_assign, variant_name, output_dir=RESULTS_DIR, show_plot=False)

    save_histograms(variant_name)

def main():
    # Controlla i parametri da linea di comando:
    # - Se viene passato "test", esegue la configurazione di test.
    # - Se viene passato una lettera, esegue quella specifica configurazione.
    # - Se non vengono passati argomenti o viene passato "all", esegue tutte le configurazioni.
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "test":
            run_test_configuration()
        elif len(arg) == 1 and arg.upper() in string.ascii_uppercase:
            run_specific_configuration(arg)
        elif arg == "all":
            run_all_configurations()
        else:
            print("Argomento non riconosciuto. Usa 'test' per il test, una lettera (A, B, ...) per una specifica configurazione, oppure 'all' per eseguire tutte le configurazioni.")
    else:
        run_all_configurations()

if __name__ == '__main__':
    main()


