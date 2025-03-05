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
- `eo`: Primo istante disponibile per servire una richiesta (inizio turno, es. 420 per il mattino o 960 per il pomeriggio).
- `ho`: Tempo residuo nel turno (inizialmente 300 minuti, cioè 5 ore).
- `wo`: Tempo di lavoro accumulato (inizialmente 0).
- `Lo`: Lista delle richieste assegnate, in cui ogni elemento è una tupla (richiesta, istante di inizio servizio).
- `current_patient`: Punto attuale in cui si trova l’operatore (inizialmente il depot).
- `cluster_id`: Indica l'area geografica o il cluster a cui l'operatore è assegnato.

### **Classe Request**  
Rappresenta una richiesta (visita a un paziente).  

**Attributi principali:**
- `i`: Identificativo della richiesta.
- `patient`: Nodo associato al paziente.
- `duration`: Durata della visita in minuti.
- `temporal_window`: Finestra temporale in cui la richiesta deve essere servita (α, β).
- `cluster_id`: Etichetta del cluster a cui il paziente appartiene, assegnata dall’algoritmo di clustering.

---

## 3. Implementazione dell’Algoritmo GRS (Greedy Routing and Scheduling)

### grs_time.py

Il modulo **grs_time.py** include le seguenti funzioni chiave:

- **`compute_travel_time(node_a, node_b)`**  
  Calcola il tempo di viaggio tra due nodi utilizzando la distanza euclidea (1 unità = 1 minuto).

- **`is_feasible(operator, request, shift_end, debug=False)`**  
  Verifica se un operatore può servire una richiesta, controllando:
  - Se l’orario di arrivo (eo + travel) rientra nella finestra temporale della richiesta.
  - Se l’assegnazione della richiesta (duration) non supera la fine del turno (shift_end) e non eccede il tempo residuo (ho).
  
  È stato aggiunto un parametro `debug` per stampare i messaggi di rifiuto solo quando necessario.

- **`filter_operators_by_cluster(request, operators)`**  
  Restringe il set degli operatori a quelli aventi lo stesso `cluster_id` della richiesta. Se nessuno corrisponde, viene usato un fallback che considera tutti gli operatori.

- **`select_best_operator_for_request(request, operators, shift_end)`**  
  Tra gli operatori pertinenti, seleziona quello che minimizza il travel time e rispetta i vincoli di fattibilità, utilizzando la funzione `is_feasible`.

- **`grs_time(operators, requests, is_morning=True)`**  
  La funzione principale che:
  1. Reinizializza lo stato degli operatori in base al turno da simulare:
     - **Turno mattutino:** `eo = 420`, `ho = 300`, `shift_end = 720`.
     - **Turno pomeridiano:** Utilizza il reset (es. `eo = 960`, `ho = 300`) e `shift_end = 1290`.
  2. Ordina le richieste per l'inizio della finestra temporale (α).
  3. Per ciascuna richiesta, seleziona l’operatore fattibile (con min travel time) e aggiorna lo stato dell’operatore:
     - Aggiorna `Lo` con la tupla (richiesta, max(eo + travel, α)).
     - Aggiorna `wo` aggiungendo il tempo di percorrenza e la durata.
     - Aggiorna `eo` e ricalcola `ho` come `shift_end - eo`.
     - Aggiorna il `current_patient` con il paziente della richiesta.
  4. Restituisce lo schedule (un dizionario {op_id: [richieste assegnate]}) e un dizionario di statistiche che conta il numero totale di richieste, quelle assegnate, non assegnate, e i motivi dei fallimenti (arrival_fail, work_fail).

---

## 4. Integrazione con il Clustering K-Medoids

### **Modello K-Medoids (in MIPClustering)**

- **Input e Calcolo:**  
  Viene generato un dataset sintetico (ad es. con `make_blobs`), e l'algoritmo K-Medoids (in `mip_clustering.py`) raggruppa i punti in K cluster, ottimizzando la somma delle distanze (o tempi) dai punti al medoid.

- **Estrazione e Rimappatura dei Cluster:**  
  Il metodo `get_cluster_labels()` estrae le etichette, che vengono poi rimappate in valori consecutivi tramite la funzione `remap_cluster_labels`, semplificando l'interpretazione e la gestione degli operatori e delle richieste.

---

## 5. Generazione delle Richieste e Modalità di Test

### **Generazione delle Richieste**

Il file **test_integration.py** offre due modalità per generare le richieste:
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


### **Selezione del Turno**

Nel test è possibile specificare se simulare il turno mattutino o pomeridiano tramite un parametro booleano (`is_morning`):
- **True:** turno mattutino (shift_end = 720).
- **False:** turno pomeridiano (shift_end = 1290, con reset dello stato degli operatori).

---

## 6. Test e Debug

- **Statistiche di Assegnazione:**  
  Al termine dell'esecuzione del GRS, il sistema restituisce:
  - **total_requests:** Numero totale di richieste elaborate.
  - **assigned:** Numero di richieste assegnate.
  - **not_assigned:** Numero di richieste non assegnate.
  - **arrival_fail:** Numero di richieste non assegnate per cui l'orario di arrivo non rientrava nella finestra temporale.
  - **work_fail:** Numero di richieste non assegnate per mancanza di tempo residuo (superamento del turno o tempo insufficiente).

---

## 7. Progressi

- **Implementazione Dinamica del Turno:**  
  Sono presenti sia il turno mattutino che quello pomeridiano, le variabili `eo`, `ho` e `shift_end`, vengono aggiornate dinamicamente.

- **Statistiche Dettagliate:**  
 Sono presenti statistiche che permettono di capire quanti e quali motivi hanno portato al fallimento dell'assegnazione di alcune richieste.

