# Clustering MIP

## 1. Obiettivi e Contesto

- **Obiettivo Principale:**  
  Integrare un modello di clustering basato su programmazione MIP (utilizzando Gurobi) con un algoritmo Greedy Routing and Scheduling (GRS) per ottimizzare l'assegnamento delle richieste agli operatori.

- **Applicazione Reale:**  
  Il sistema è pensato per ottimizzare gli spostamenti degli infermieri territoriali. Ogni paziente è rappresentato da un nodo (con coordinate) e le distanze (τ₍ᵢⱼ₎) includono anche il tempo di percorrenza in minuti. L'idea è raggruppare i pazienti in cluster, in modo che ciascun infermiere possa servire un gruppo di pazienti vicini, riducendo i tempi di spostamento e migliorando l'efficienza.

---

## 2. Modelli e Classi Definite

### **Classe Node**  
Rappresenta un paziente con un identificativo e coordinate.

### **Classe Operator**  
Rappresenta l’operatore.

**Attributi principali:**
- `id`: Identificativo univoco.
- `home`: Nodo di partenza (depot).
- `work_time`: Tempo di lavoro residuo (default 300 minuti).
- `t0`: Il primo momento disponibile per l'operatore per servire una richiesta, 420 = 7:00.
- `current_patient`: Punto attuale in cui si trova l'operatore (inizialmente impostato al depot).
- `cluster_id`: Indica l'area geografica o il cluster a cui l'operatore è assegnato.

### **Classe Request**  
Rappresenta una richiesta (visita a un paziente).  

**Attributi principali:**
- `i`: Identificativo della richiesta.
- `patient`: Nodo associato al paziente (è stato rinominato da “origin” per maggiore chiarezza).
- `duration`: Durata della visita in minuti.
- `temporal_window`: Finestra temporale in cui la richiesta deve essere servita (α, β).
- `cluster_id`: Etichetta del cluster a cui il paziente appartiene, assegnata dall’algoritmo di clustering.

---

## 3. Implementazione dell’Algoritmo GRS (Greedy Routing and Scheduling)

Il modulo **grs.py** include le seguenti funzioni chiave:

- **`compute_travel_time(node_a, node_b)`**  
  Calcola il tempo di viaggio tra due nodi, utilizzando la distanza euclidea.

- **`is_feasible(operator, request)`**  
  Verifica se un operatore può servire una richiesta controllando due condizioni:
  - L'orario di arrivo (calcolato come `t0 + travel_time`) deve rientrare nella finestra temporale della richiesta.
  - La `duration` della richiesta non deve superare il `work_time` residuo dell'operatore.
  
  Il metodo include stampe di debug per evidenziare il motivo per cui una richiesta non è fattibile (ad es. finestra temporale non rispettata o tempo richiesto eccessivo).


- **`filter_operators_by_cluster(request, operators)`**  
  Restringe il set degli operatori ai soli quelli aventi lo stesso `cluster_id` della richiesta. Se nessun operatore corrisponde, viene usato un fallback che considera tutti gli operatori.

- **`select_best_operator_for_request(request, operators)`**  
  Utilizza il filtro per cluster e, tra gli operatori pertinenti, seleziona quello che minimizza il `travel_time` e rispetta i vincoli di fattibilità.

- **`grs(operators, requests)`**  
  Funzione principale che:
  1. Ordina le richieste per il valore α della finestra temporale.
  2. Per ciascuna richiesta, seleziona l’operatore migliore (usando il filtro per cluster).
  3. Aggiorna lo stato dell’operatore (riducendo il `work_time`, aggiornando `t0` e `current_patient`).
  4. Restituisce uno schedule (un dizionario) che mappa ogni operatore alle richieste assegnate.

---

## 4. Integrazione con il Clustering K-Medoids

### **Modello K-Medoids (in MIPClustering)**

- **Input e Calcolo:**  
  Viene generato un dataset sintetico (ad es. utilizzando `make_blobs`), e l'algoritmo K-Medoids (implementato in `mip_clustering.py`) viene utilizzato per raggruppare i punti in un numero K di cluster.

- **Estrazione dei Cluster:**  
  Il metodo `get_cluster_labels()` estrae per ogni punto un'etichetta che corrisponde all'indice del medoid a cui il punto è stato assegnato.  
  **Nota:** Questi cluster_id iniziali possono essere numeri sparsi (es. 21, 41, 51) che rappresentano gli indici originali dei medoids.

### **Rimappatura dei Cluster ID**

Per rendere le etichette consecutive (0, 1, 2, ...), è stata implementata la funzione:
  
```python
def remap_cluster_labels(cluster_labels):
    unique_medoids = sorted(set(cluster_labels))
    medoid_to_new_id = {medoid: i for i, medoid in enumerate(unique_medoids)}
    new_cluster_labels = [medoid_to_new_id[cluster] for cluster in cluster_labels]
    return new_cluster_labels, medoid_to_new_id
```

Questa funzione crea una mappatura dai vecchi cluster_id (gli indici dei medoids) a etichette consecutive, semplificando l'interpretazione e la gestione degli operatori e delle richieste.

---

## 5. Generazione delle Richieste e Modalità di Test

### **Modalità di Generazione delle Richieste**

Per testare il sistema si può utilizzare il file `test_integration.py`, che implementa due modalità:

- **`simple_requests`**  
  Genera richieste con una finestra temporale fissa (ad es. da 7:00 a 13:00, cioè (420, 780)).

- **`random_requests`**  
  Genera richieste con finestre temporali variabili.  
  - L'orario di inizio (`alpha`) viene scelto casualmente tra un minimo e un massimo (ad es. tra 420 e 450).
  - L'orario di fine (`beta`) viene scelto casualmente tra `alpha + un offset minimo` (es. 40 minuti) e un massimo (ad es. 780, cioè 13:00).

### **Selezione della Modalità di Test**

Nel file di test, è prevista una variabile booleana (ad esempio `use_random`) nel main che permette, se impostata a `True`, di attivare l'implementazione random (attivata di default). È possibile configurare i valori delle richieste con i parametri:
- `alpha_min=420` e `alpha_max=450`: orario di inizio minimo e massimo, in minuti (tra le 7:00 e le 7:30)
- `beta_min_offset=40`: l'orario di fine è almeno 40 min dopo alpha
- `beta_max=780`: l'orario di fine massimo (13:00, per la mattina)

---

## 6. Test e Validazioni

- **Esecuzione dei Test:**  
  Sono stati creati script di test che integrano:
  - La generazione dei nodi tramite `make_blobs`.
  - L'esecuzione del clustering K-Medoids e la rimappatura dei cluster_id.
  - La creazione di oggetti Node, Request (con cluster_id) e Operator (assegnando a ciascun operatore un cluster_id basato sul depot o su altri criteri).
  - L'esecuzione del GRS, con il filtro dinamico che restringe la ricerca degli operatori al cluster della richiesta.

- **Messaggi di Debug:**  
  La funzione `is_feasible` include stampe di log che aiutano a diagnosticare perché alcune richieste non vengono assegnate (ad esempio, perché l'orario di arrivo supera la finestra temporale).

- **Risultati:**  
  I test hanno mostrato che il sistema assegna correttamente le richieste agli operatori in base al cluster e che, modificando i parametri (durate, finestre temporali), è possibile analizzare e ottimizzare l'assegnamento.
