import gurobipy as gp
from gurobipy import GRB, quicksum
import numpy as np
from scipy.spatial import distance_matrix

class MIPClustering:
    def __init__(self, points, K):
        """
        Inizializza l'istanza per il clustering MIP.
        
        Parametri:
        - points: array numpy contenente i dati (n_points x n_features).
        - K: numero di cluster desiderato.
        """
        self.N = points.shape[0]  # Numero di punti
        self.K = K                # Numero di cluster
        # Calcola la matrice delle distanze (tau) tra ogni coppia di punti utilizzando la distanza euclidea
        self.tau = distance_matrix(points, points)
        # Big-M per la linearizzazione (la massima distanza tra due punti)
        self.M = np.max(self.tau)
        self.model = None  # Il modello Gurobi verrà creato nei metodi seguenti
        self.x = None      # Variabili di assegnazione dei punti ai cluster
        self.y = None      # Variabili che indicano il centroide in ogni cluster (solo per K-Means)

    def create_kmedoids_model(self):
        n = len(self.tau)
        model = gp.Model("k_medoids")
        
        # Variabili di assegnazione: x[i,j] = 1 se il punto i è assegnato al medoid j
        self.x = model.addVars(n, n, vtype=GRB.BINARY, name="x")
        # Variabili che indicano se il punto j è scelto come medoid
        self.y = model.addVars(n, vtype=GRB.BINARY, name="y")
        
        # Vincolo 1: ogni punto deve essere assegnato a un unico medoid
        model.addConstrs(
            (quicksum(self.x[i, j] for j in range(n)) == 1 for i in range(n)),
            name="assignment"
        )
        
        # Vincolo 2: esattamente K medoids
        model.addConstr(
            quicksum(self.y[j] for j in range(n)) == self.K,
            name="k_clusters"
        )
        
        # Vincolo 3: un punto i può essere assegnato a j solo se j è scelto come medoid
        model.addConstrs(
            (self.x[i, j] <= self.y[j] for i in range(n) for j in range(n)),
            name="link"
        )
        
        # Obiettivo: minimizzare la somma delle distanze tra i punti e il loro medoid assegnato
        # Poiché self.tau contiene già le distanze, basta usarlo direttamente.
        model.setObjective(
            quicksum(self.tau[i][j]*self.x[i, j] for i in range(n) for j in range(n)),
            GRB.MINIMIZE
        )
        
        # Salva il modello e le variabili nell'istanza, se necessario
        self.model = model

    """   
    def create_minimax_model(self):
        
        self.model = gp.Model("MinimaxClustering")
        # x[i,k] = 1 se il punto i è assegnato al cluster k.
        self.x = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="x")
        # d[k] rappresenta il diametro del cluster k (la distanza massima tra due punti assegnati a quel cluster).
        d = self.model.addVars(self.K, vtype=GRB.CONTINUOUS, name="d")
        
        # Vincolo 1: Ogni punto deve essere assegnato a un solo cluster.
        for i in range(self.N):
            self.model.addConstr(gp.quicksum(self.x[i, k] for k in range(self.K)) == 1, f"assign_{i}")
        
        # Vincolo 2: Ogni cluster deve avere almeno un punto.
        for k in range(self.K):
            self.model.addConstr(gp.quicksum(self.x[i, k] for i in range(self.N)) >= 1, f"cluster_nonempty_{k}")
        
        # Vincoli Big-M per definire il diametro di ogni cluster:
        # Per ogni cluster k e per ogni coppia di punti (i, j) (con j > i per evitare ripetizioni),
        # se entrambi i punti appartengono a k (x[i,k] e x[j,k] = 1) allora la distanza tau[i][j] deve essere
        # minore o uguale a d[k]. Il termine -M*(2 - x[i,k] - x[j,k]) "disattiva" il vincolo se almeno uno dei due non appartiene a k.
        for k in range(self.K):
            for i in range(self.N):
                for j in range(i+1, self.N):
                    self.model.addConstr(
                        d[k] >= self.tau[i][j] - self.M * (2 - self.x[i, k] - self.x[j, k]),
                        f"diam_{k}_{i}_{j}"
                    )
        
        # Funzione obiettivo: Minimizzare la somma dei diametri dei cluster, diviso il numero di cluster.
        obj = gp.quicksum(d[k] for k in range(self.K)) / self.K
        self.model.setObjective(obj, GRB.MINIMIZE)


    # Aggiunta di un metodo per creare il modello MIP per K-Means pesato
    def create_weighted_kmeans_model(self, weights):
     
        self.model = gp.Model("WeightedKMeansMIP")
        
        # Variabili: x indica l'assegnazione, y indica il centroide
        self.x = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="x")
        self.y = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="y")
        
        # Variabili per le distanze pesate
        d = self.model.addVars(self.N, self.K, vtype=GRB.CONTINUOUS, name="d")
        
        # Vincolo: ogni punto deve essere assegnato ad un solo cluster
        for i in range(self.N):
            self.model.addConstr(gp.quicksum(self.x[i, k] for k in range(self.K)) == 1, f"assign_{i}")
        
        # Vincolo: ogni cluster deve avere esattamente un centroide
        for k in range(self.K):
            self.model.addConstr(gp.quicksum(self.y[j, k] for j in range(self.N)) == 1, f"centroid_{k}")
        
        # Vincolo: un punto può essere centroide solo se è assegnato al cluster
        for j in range(self.N):
            for k in range(self.K):
                self.model.addConstr(self.y[j, k] <= self.x[j, k], f"centroid_assign_{j}_{k}")
        
        # Vincolo: definizione della distanza pesata
        for i in range(self.N):
            for k in range(self.K):
                # d[i,k] = weights[i] * sum_j (tau[i][j] * weights[j] * y[j,k])
                self.model.addConstr(
                    d[i, k] == weights[i] * gp.quicksum(self.tau[i][j] * weights[j] * self.y[j, k] for j in range(self.N)),
                    f"dist_weighted_{i}_{k}"
                )
        
        # Funzione obiettivo: minimizzare la media delle distanze pesate
        obj = gp.quicksum(d[i, k] for i in range(self.N) for k in range(self.K)) / self.K
        self.model.setObjective(obj, GRB.MINIMIZE)

    """

    def solve(self, time_limit=10000):
        """
        Risolve il modello MIP impostato (sia per K-Means che per Minimax)
        impostando un limite temporale per la risoluzione.
        
        Parametri:
        - time_limit: tempo massimo in secondi per la risoluzione del modello.
        """
        self.model.setParam('TimeLimit', time_limit)
        self.model.optimize()
    
    def get_clusters(self):
        """
        Estrae i cluster dalla soluzione ottimale.
        
        Ritorna:
        - Un dizionario in cui ogni chiave è l'ID del cluster (0, 1, ..., K-1)
          e il valore è la lista degli indici dei punti assegnati a quel cluster.
        """

        medoids = {}
        clusters = {}
        if self.model.status == GRB.OPTIMAL:
            ones = [j for j in range(self.N) if self.y[j].X > 0.5]
            for k in range(self.K):
                medoids[k] = ones[k]
                
            for k in range(self.K):
                # Se la variabile x[i,k] è maggiore di 0.5 (dato che è binaria) il punto i è assegnato a cluster k.
                clusters[k] = [i for i in range(self.N) if self.x[i, medoids[k]].X > 0.5]

        return clusters


    def get_medoids(self):
        """
        Estrae gli indici dei medoid dalla soluzione ottimale.
        Ritorna:
        - Una lista degli indici dei punti che sono medoid.
        """
        medoids = [j for j in range(self.N) if self.y[j].X > 0.5]
        return medoids
    

    def get_cluster_labels(self) -> list:
        """
        Estrae le etichette di cluster per ogni punto, in base alla soluzione
        del modello K-Medoids. Per ogni punto i, l'etichetta è l'indice j per cui
        la variabile x[i,j] è pari a 1.
        
        :return: Una lista di lunghezza N, dove l'elemento in posizione i è il cluster_id
                (l'indice del medoid assegnato) per il punto i.
        """
        
        labels = [-1] * self.N  # Lista per i cluster, -1 indica nessuna assegnazione.
        for i in range(self.N):
            for j in range(self.N):
                
                if self.x[i, j].X > 0.5: 
                    labels[i] = j
                    break
        return labels


    def remap_cluster_labels(cluster_labels):
        """
        Converte i cluster_id dei medoids nei valori consecutivi (0, 1, 2, ...)
        invece degli indici originali dei medoids.

        :param cluster_labels: Lista dei cluster_id originali (indice dei medoids)
        :return: Lista con cluster_id rinumerati e mappa di conversione.
        """
        unique_medoids = sorted(set(cluster_labels))  # Ottieni i medoids unici ordinati
        medoid_to_new_id = {medoid: i for i, medoid in enumerate(unique_medoids)}  # Mappatura

        # Crea una nuova lista con cluster_id consecutivi
        new_cluster_labels = [medoid_to_new_id[cluster] for cluster in cluster_labels]

        return new_cluster_labels, medoid_to_new_id
