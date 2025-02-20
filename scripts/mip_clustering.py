import gurobipy as gp
from gurobipy import GRB
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

    def create_kmeans_model(self):
        """Crea il modello MIP per il clustering K-Means."""
        self.model = gp.Model("KMeansMIP")
        
        # ---------------------------
        # Definizione delle variabili
        # ---------------------------
        # x[i,k] = 1 se il punto i è assegnato al cluster k, 0 altrimenti.
        self.x = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="x")
        # y[j,k] = 1 se il punto j è scelto come centroide del cluster k, 0 altrimenti.
        self.y = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="y")
        # d[i,k]: distanza calcolata come la somma pesata delle distanze tra il punto i e il centroide del cluster k.
        d = self.model.addVars(self.N, self.K, vtype=GRB.CONTINUOUS, name="d")
        
        # ---------------------------
        # Vincoli del modello K-Means
        # ---------------------------
        # Vincolo 1: Ogni punto deve essere assegnato a un solo cluster.
        for i in range(self.N):
            self.model.addConstr(gp.quicksum(self.x[i, k] for k in range(self.K)) == 1, f"assign_{i}")
        
        # Vincolo 2: Ogni cluster deve avere esattamente un centroide.
        for k in range(self.K):
            self.model.addConstr(gp.quicksum(self.y[j, k] for j in range(self.N)) == 1, f"centroid_{k}")
        
        # Vincolo 3: Un punto può essere centroide di un cluster solo se è assegnato a quel cluster.
        for j in range(self.N):
            for k in range(self.K):
                self.model.addConstr(self.y[j, k] <= self.x[j, k], f"centroid_assign_{j}_{k}")
        
        # Vincolo 4: Calcolo delle distanze d[i,k] per ogni punto i e cluster k.
        # La distanza viene calcolata come la somma delle distanze tra il punto i e tutti i punti j,
        # pesata dalla variabile y[j,k] (che indica il centroide del cluster).
        for i in range(self.N):
            for k in range(self.K):
                self.model.addConstr(
                    d[i, k] == gp.quicksum(self.tau[i][j] * self.y[j, k] for j in range(self.N)),
                    f"dist_{i}_{k}"
                )
        
        # ---------------------------
        # Funzione obiettivo
        # ---------------------------
        # Minimizzare la somma delle distanze per ogni punto e cluster, diviso il numero di cluster.
        obj = gp.quicksum(d[i, k] for i in range(self.N) for k in range(self.K)) / self.K
        self.model.setObjective(obj, GRB.MINIMIZE)
    
    def create_minimax_model(self):
        """Crea il modello MIP per il clustering Minimax."""
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
    
    def solve(self, time_limit=300):
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
        clusters = {}
        if self.model.status == GRB.OPTIMAL:
            for k in range(self.K):
                # Se la variabile x[i,k] è maggiore di 0.5 (dato che è binaria) il punto i è assegnato a cluster k.
                clusters[k] = [i for i in range(self.N) if self.x[i, k].X > 0.5]
        return clusters
