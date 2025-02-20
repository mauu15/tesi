# Clustering MIP

L'obiettivo è implementare due modelli di clustering basati su programmazione MIP (utilizzando Gurobi):

- **K-Means MIP:** Minimizza la somma pesata delle distanze tra ogni punto e il centroide del cluster.
- **Minimax MIP:** Minimizza il diametro massimo dei cluster, cercando di ottenere gruppi più compatti.

---

## Struttura dei File

- **test_k_means.py:**  
  Script principale che genera dati sintetici, istanzia i modelli MIP (definiti in `mip_clustering.py`), risolve i modelli per diversi valori di K e richiama le funzioni di visualizzazione.

- **mip_clustering.py:**  
  Definisce la classe `MIPClustering` che implementa i modelli MIP.  
  - Il metodo `create_kmeans_model()` imposta il modello K-Means MIP.  
  - Il metodo `create_minimax_model()` imposta il modello Minimax MIP.  
  - Il metodo `solve()` risolve il modello tramite Gurobi e `get_clusters()` estrae l'assegnazione dei punti ai cluster.

- **visualization.py:**  
  Contiene le funzioni di visualizzazione dei risultati:
  - `plot_clusters()` genera e salva il plot del clustering KMeans.
  - `plot_mip_clusters()` genera e salva il plot del clustering ottenuto con i modelli MIP (attualmente rinominato in "minimax_clusters.png").
  Le immagini vengono salvate nella cartella "tesi" per mantenere il tutto organizzato.

---

## Flusso di Lavoro

1. **Avvio dello Script Principale (`test_k_means.py`):**
   - **Generazione dei dati:**  
     Viene creato un dataset sintetico (ad esempio, 100 punti in 2 dimensioni) tramite `make_blobs`.
   
   - **Costruzione e Risoluzione dei Modelli:**  
     Per ogni valore di K (2, 3, 4):
     - Viene istanziata la classe `MIPClustering` (definita in `mip_clustering.py`).
     - Vengono creati e risolti i modelli:
       - **K-Means MIP:** Utilizzando `create_kmeans_model()`, il modello assegna ogni punto ad un cluster e seleziona il centroide.
       - **Minimax MIP:** Utilizzando `create_minimax_model()`, il modello assegna i punti e minimizza il diametro massimo dei cluster.
     - Dopo la risoluzione, il metodo `get_clusters()` estrae i cluster ottenuti.
   
   - **Visualizzazione dei Risultati:**  
     I cluster ottenuti vengono passati alle funzioni in `visualization.py`, che:
     - Riducono la dimensionalità dei dati tramite PCA.
     - Generano i plot dei cluster e li salvano (ad esempio, "kmeans_clusters.png" per il modello K-Means e "minimax_clusters.png" per il modello Minimax).

2. **Organizzazione dei File di Output:**  
   Le immagini generate vengono salvate nella cartella "tesi" (la stessa cartella in cui si trovano gli script) per mantenere l'home del server ordinata e il progetto ben organizzato.

---

## Lavoro Svolto Finora

- **Implementazione dei modelli MIP:**  
  Realizzazione di `mip_clustering.py` con i modelli K-Means e Minimax MIP utilizzando Gurobi.

- **Sviluppo dello script principale:**  
  Creazione di `test_k_means.py` per generare dati sintetici, eseguire i modelli e visualizzare i risultati.

- **Visualizzazione dei risultati:**  
  Realizzazione di `visualization.py` per ridurre i dati con PCA e generare i plot dei cluster.

- **Organizzazione dei file:**  
  Configurazione del salvataggio delle immagini nella cartella "tesi" per mantenere il progetto organizzato.

---

## Prossimi Passi

- **Analisi dei plot generati:**  
  Esaminare i file immagine (ad esempio, "minimax_clusters.png") e discuterne l'interpretazione con la professoressa.

- **Implementazione di metriche di valutazione:**  
  Aggiungere metriche (es. silhouette score) per valutare la qualità dei cluster.

- **Test su dataset differenti:**  
  Provare i modelli su dataset reali o sintetici con caratteristiche diverse per verificarne la robustezza.

- **Aggiornamenti e ottimizzazioni:**  
  Continuare a migliorare il codice, aggiungendo commenti e ottimizzando i parametri di Gurobi se necessario.

---

Questo file verrà aggiornato man mano che il progetto procede.  
Sentiti libero di modificarlo e ampliarlo per tenere traccia di tutte le modifiche e i progressi.

