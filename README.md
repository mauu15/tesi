# Clustering MIP

L'obiettivo è implementare due modelli di clustering basati su programmazione MIP (utilizzando Gurobi):

- **K-Means MIP:** Minimizza la somma pesata delle distanze tra ogni punto e il centroide del cluster.
- **Minimax MIP:** Minimizza il diametro massimo dei cluster, cercando di ottenere gruppi più compatti.

---

## Struttura dei File

- **test_models.py:**  
  Script principale che genera dati sintetici, istanzia i modelli MIP (definiti in `mip_clustering.py`), risolve i modelli per diversi valori di K e richiama le funzioni di visualizzazione.  

- **mip_clustering.py:**  
  Definisce la classe `MIPClustering` che implementa i modelli MIP.  
  - Il metodo `create_kmeans_model()` imposta il modello K-Means MIP.
  - Il metodo `create_minimax_model()` imposta il modello Minimax MIP.
  - Il metodo `create_weighted_kmeans_model(weights)` implementa il K-Means pesato, utilizzando un array di pesi per modulare il calcolo delle distanze.
  - Il metodo `solve()` risolve il modello tramite Gurobi e `get_clusters()` estrae l'assegnazione dei punti ai cluster.

- **visualization.py:**  
  Contiene le funzioni di visualizzazione dei risultati:
  - `plot_clusters()` genera e salva il plot del clustering KMeans.
  - `plot_mip_clusters()` genera e salva il plot del clustering ottenuto con i modelli MIP (ad es. "minimax_clusters.png").
  Le immagini vengono salvate nella cartella "imgs".

---

## Flusso di Lavoro

1. **Avvio dello Script Principale (`test_models.py`):**
   - **Generazione dei dati:**  
     Viene creato un dataset sintetico (ad esempio, 150 punti in 2 dimensioni) tramite `make_blobs`.
   
   - **Costruzione e Risoluzione dei Modelli:**  
     Per ogni valore di K (ad esempio 2, 3, 4):
     - Viene istanziata la classe `MIPClustering` (definita in `mip_clustering.py`).
     - Vengono creati e risolti i modelli:
       - **K-Means MIP:** Utilizzando `create_kmeans_model()`, il modello assegna ogni punto a un cluster e seleziona il centroide.
       - **Minimax MIP:** Utilizzando `create_minimax_model()`, il modello assegna i punti e minimizza il diametro massimo dei cluster.
     - Dopo la risoluzione, il metodo `get_clusters()` estrae i cluster ottenuti.
   
   - **Visualizzazione dei Risultati:**  
     I cluster vengono passati alle funzioni in `visualization.py` che:
     - Riducono la dimensionalità dei dati tramite PCA.
     - Generano i plot dei cluster e li salvano (ad esempio, "kmeans_clusters.png" per il modello K-Means, "minimax_clusters.png" per il modello Minimax).

2. **Organizzazione dei File di Output:**  
   Le immagini generate vengono salvate nella cartella "tesi" (nello specifico in "tesi/imgs" con le sottocartelle "kmeans" e "minimax") per mantenere l'home del server ordinata e il progetto ben organizzato.

---

## Lavoro Svolto Finora

- **Implementazione dei modelli MIP:**  
  Realizzazione di `mip_clustering.py` con i modelli K-Means e Minimax MIP utilizzando Gurobi.

- **Sviluppo dello script principale:**  
  Creazione di `test_models.py` per generare dati sintetici, eseguire i modelli e visualizzare i risultati.

- **Visualizzazione dei risultati:**  
  Realizzazione di `visualization.py` per ridurre i dati con PCA e generare i plot dei cluster.

- **Organizzazione dei file:**  
  Configurazione del salvataggio delle immagini nella cartella "tesi/imgs" per mantenere il progetto organizzato.

---

## Estensione: K-Means Pesato

Una variante del K-Means MIP che utilizza dei pesi per "modulare" le distanze. In pratica, invece di usare la sola distanza \( \tau_{ij} \) tra i punti, ora la distanza viene calcolata come:

$$ 
d[i,k] = w_i \times \sum_j \bigl( \tau[i][j] \times w_j \times y[j,k] \bigr)
$$


Qui:
- **\(w_i\)** è il peso del punto \(i\)
- **\(w_j\)** è il peso del punto \(j\), usato per ponderare la distanza nel caso in cui \(j\) venga scelto come centroide.
- **\(y[j,k]\)** è la variabile binaria che indica se il punto \(j\) è il centroide del cluster \(k\).

I pesi, generati casualmente tra 0.5 e 1.0, vengono usati per influenzare il calcolo delle distanze, permettendoci di testare come questa variazione possa modificare gli assegnamenti dei cluster.

Nel file di test (`test_models.py`), genero i pesi così:

```python
weights = np.random.uniform(0.5, 1.0, size=X.shape[0])
```

e poi uso il nuovo metodo `create_weighted_kmeans_model(weights)` (definito in `mip_clustering.py`) per testare questa versione pesata. Così possiamo confrontare i risultati del modello base con quelli del modello pesato e vedere se l'introduzione dei pesi offre qualche vantaggio o una diversa struttura dei cluster.
