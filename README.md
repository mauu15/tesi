# Euristiche per problemi di pianificazione di servizi di assistenza domiciliare su larga scala

## 1. Obiettivi e Contesto

- **Obiettivo Principale:**\
  Integrare un modello di clustering basato su programmazione MIP (utilizzando Gurobi) con un algoritmo Greedy Routing and Scheduling (GRS) per ottimizzare l'assegnamento delle richieste agli operatori.

- **Applicazione Reale:**\
  Il sistema è pensato per ottimizzare gli spostamenti degli infermieri territoriali. Ogni paziente è rappresentato da un nodo (con coordinate) e le distanze (τᵢⱼ) includono anche il tempo di percorrenza in minuti. L'idea è raggruppare i pazienti in cluster, in modo che ciascun infermiere possa servire un gruppo di pazienti vicini, riducendo i tempi di spostamento e migliorando l'efficienza.

---

## 2. Modelli e Classi Definite

### **Classe Node**

Rappresenta un paziente con un identificativo e coordinate.

### **Classe Operator**

Rappresenta l’operatore.

**Attributi principali:**

- `id`: Identificativo univoco.
- `home`: Nodo di partenza (depot).
- `eo`: Primo istante disponibile per servire una richiesta (es. 420 minuti corrispondenti alle 7:00).
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

Lo script **`grs_variants.py`** implementa le diverse varianti dell’approccio Greedy Routing and Scheduling per assegnare le richieste agli operatori in base ai dati reali (inclusa una matrice delle distanze letta da file JSON).

### 3.1 Funzioni di Supporto

1. **`parse_time_to_minutes(time_value)`**  
   Converte un orario scritto nel formato `H.MM` (es. `15.55` → 15:55 → 955 minuti) in minuti interi. Se il valore non contiene un punto, lo interpreta come ore intere (es. `8` → `480` minuti).

2. **`get_distance(id1, id2)`** e **`compute_travel_time(op, req, patients)`**  
   - `get_distance` legge una matrice delle distanze (strutturata come un dizionario di coppie `(id_min, id_max) → distanza`). Ritorna `∞` se la chiave non è trovata.
   - `compute_travel_time` individua il paziente associato alla richiesta (tramite `req["project_id"]`), poi calcola il tempo di spostamento usando `get_distance(op["id"], patient["id"])`.

3. **`compute_cost(variant, op, t_i, tau)`**  
   Calcola il costo in base alla variante GRS selezionata:
   - **Time**: `return tau`  (minimizza gli spostamenti)
   - **Saturami**: `ho_final = op["ho"] - t_i` → `return ho_final`  (minimizza il tempo residuo, massimizza la saturazione)
   - **LasciamiInPace**: `ho_final = op["ho"] - t_i` → `return -ho_final`  (massimizza il tempo residuo)
   - **TradeOff**: `return op["wo"] + tau + t_i`  (minimizza la somma tra lavoro accumulato, spostamento e durata)

4. **`set_operator_state_morning(operator)`** e **`set_operator_state_afternoon(operator)`**  
   - `set_operator_state_morning` reimposta l’operatore per il turno mattutino (7:00 → 420 minuti) inizializzando `eo = 420`, `ho = 300`, `wo = 0`, e azzerando l’elenco di richieste (`Lo`).
   - `set_operator_state_afternoon` reimposta l’operatore per il turno pomeridiano. Se l’operatore ha già lavorato al mattino (`worked_morning == True`), il turno parte alle 18:00 (1080 min), altrimenti alle 16:00 (960 min). In entrambi i casi, `ho = 300` e `wo = 0`.

### 3.2 Funzione Principale `grs(...)`

La funzione **`grs(variant, operators, requests, patients, shift_end=720)`** implementa il nucleo dell’algoritmo Greedy Routing and Scheduling per un singolo turno (mattina o pomeriggio):
1. Per ogni operatore, se non sono inizializzate, imposta le variabili (`eo`, `ho`, `wo`, `Lo`).
2. Ordina le richieste in base all’orario minimo di inizio (`min_time_begin`).
3. Per ciascuna richiesta:
   - Converte in minuti `alpha_i = parse_time_to_minutes(req["min_time_begin"])` e `beta_i = parse_time_to_minutes(req["max_time_begin"])`.
   - Calcola la durata `t_i = req["duration"]`.
   - Per ogni operatore, valuta lo spostamento `travel_time = compute_travel_time(op, req, patients)`, controlla se rispettano i vincoli di orario (`op["eo"] + travel_time <= beta_i`, `t_i <= op["ho"]`) e se non supera `op["max_weekly_hours"]`.
   - Usa `compute_cost(variant, op, t_i, travel_time)` per trovare l’operatore con il costo minore (secondo la variante GRS scelta).
   - Se trova un operatore fattibile, aggiorna il suo stato:
     - `op["wo"] += (t_i + travel_time)`
     - `op["eo"] = finish_time = max(arrival_time, alpha_i) + t_i`
     - `op["ho"] = shift_end - op["eo"]`
     - `op["Lo"].append(req["id"])`
     - `op["weekly_worked"] += (t_i + travel_time)`
4. Restituisce un dizionario `assignments` che mappa `op_id → lista di request_id` assegnate.

### 3.3 Pianificazione su più Giorni

Per simulare più giornate di lavoro, si utilizza **`run_grs_for_week(variant, operators, requests, patients)`**, che:
1. Inizializza gli operatori per la settimana, azzerando o impostando i campi utili (`weekly_worked`, `worked_morning`, ecc.).
2. Per ogni giorno (0..6):
   - Filtra le richieste di quel giorno.
   - Esegue un turno mattutino chiamando `set_operator_state_morning(op)` per ogni operatore, poi `grs(...)` con `shift_end=720`.
   - Memorizza le richieste assegnate al mattino e marca `op["worked_morning"] = True` per chi ha effettivamente lavorato.
   - Esegue un turno pomeridiano chiamando `set_operator_state_afternoon(op)` per ogni operatore, poi `grs(...)` con `shift_end=1290`.
   - Accumula i minuti lavorati mattina/pomeriggio.
3. Ritorna il cumulativo delle assegnazioni settimanali.

Infine **`display_assignments_with_shifts(operators)`** costruisce un DataFrame pandas con le richieste effettuate da ciascun operatore, separando mattina e pomeriggio, e calcolando il totale di ore.

In tutte le varianti (Time, Saturami, LasciamiInPace, TradeOff), la differenza sta nella funzione `compute_cost` che definisce la priorità con cui viene scelto l’operatore.

## 4. Integrazione con il Clustering K-Medoids

### **Modello K-Medoids (in MIPClustering)**

- **Input e Calcolo:**\
  Viene utilizzato un dataset reale o sintetico (in precedenza generato con ad es. `make_blobs`), e l'algoritmo K-Medoids (in `mip_clustering.py`) raggruppa i punti in K cluster, ottimizzando la somma delle distanze o dei tempi dai punti al medoid.

- **Estrazione e Rimappatura dei Cluster:**\
  Il metodo `get_cluster_labels()` estrae le etichette, che vengono poi rimappate in valori consecutivi tramite la funzione `remap_cluster_labels`, semplificando l'interpretazione e la gestione di operatori e richieste.

---

## 5. Generazione delle Richieste e Modalità di Test

Nel progetto si è lavorato su un dataset reale (coordinate reali e distanze pre-calcolate).
È anche possibile generare richieste fittizie con finestre temporali e coordinate casuali. La configurazione delle richieste (finestra temporale `α–β`, durata `ti`, ecc.) può avvenire tramite parametri nel codice.

---

<!-- 
## 6. Test e Debug

- **Statistiche di Assegnazione:**\
  Al termine dell’esecuzione del GRS (in una delle varianti), il sistema restituisce un dizionario con:
  - `total_requests`: quante richieste totali sono state elaborate.
  - `assigned`: quante sono state assegnate correttamente.
  - `not_assigned`: quante non sono state assegnate.
  - `arrival_fail`: quante non assegnate per mancato rispetto delle finestre temporali.
  - `work_fail`: quante non assegnate per mancanza di tempo residuo o superamento orario di turno.

Questo consente di valutare rapidamente l’efficacia dell’euristica adottata.

--->

## 6. Dati reali e varianti

- **Implementazione con Dati Reali:**\
  Il sistema legge dati da un file contenente informazioni su distanze e richieste reali.

<!---
- **Statistiche Dettagliate:**\
  Permettono di capire quanti e quali motivi hanno portato al fallimento dell’assegnazione di alcune richieste, facilitando il debugging e l’ottimizzazione dell’algoritmo. --->

- **Varianti GRS Avanzate:**\
  Il file `grs_variants.py` racchiude in un'unica struttura le quattro varianti GRS, rendendo il codice modulare e facilmente estendibile.

