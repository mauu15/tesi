import gurobipy as gp
from gurobipy import GRB
import numpy as np
from scipy.spatial import distance_matrix

class MIPClustering:
    def __init__(self, points, K):
        self.N = points.shape[0]
        self.K = K
        self.tau = distance_matrix(points, points)
        self.M = np.max(self.tau)
        self.model = None
        self.x = None
        self.y = None
    
    def create_kmeans_model(self):
        """Crea il modello MIP per K-Means"""
        self.model = gp.Model("KMeansMIP")
        
        # Variabili
        self.x = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="x")
        self.y = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="y")
        d = self.model.addVars(self.N, self.K, vtype=GRB.CONTINUOUS, name="d")
        
        # Vincoli
        # Ogni punto assegnato a un cluster
        for i in range(self.N):
            self.model.addConstr(gp.quicksum(self.x[i, k] for k in range(self.K)) == 1, f"assign_{i}")
        
        # Ogni cluster ha un centroide
        for k in range(self.K):
            self.model.addConstr(gp.quicksum(self.y[j, k] for j in range(self.N)) == 1, f"centroid_{k}")
        
        # Vincolo centroide nel cluster
        for j in range(self.N):
            for k in range(self.K):
                self.model.addConstr(self.y[j, k] <= self.x[j, k], f"centroid_assign_{j}_{k}")
        
        # Calcolo distanze
        for i in range(self.N):
            for k in range(self.K):
                self.model.addConstr(
                    d[i, k] == gp.quicksum(self.tau[i][j] * self.y[j, k] for j in range(self.N)),
                    f"dist_{i}_{k}"
                )
        
        # Funzione obiettivo
        obj = gp.quicksum(d[i, k] for i in range(self.N) for k in range(self.K)) / self.K
        self.model.setObjective(obj, GRB.MINIMIZE)
        
    def create_minimax_model(self):
        """Crea il modello MIP per Minimax Clustering"""
        self.model = gp.Model("MinimaxClustering")
        self.x = self.model.addVars(self.N, self.K, vtype=GRB.BINARY, name="x")
        d = self.model.addVars(self.K, vtype=GRB.CONTINUOUS, name="d")
        
        # Vincoli
        for i in range(self.N):
            self.model.addConstr(gp.quicksum(self.x[i, k] for k in range(self.K)) == 1, f"assign_{i}")
        
        for k in range(self.K):
            self.model.addConstr(gp.quicksum(self.x[i, k] for i in range(self.N)) >= 1, f"cluster_nonempty_{k}")
        
        # Big-M constraints
        for k in range(self.K):
            for i in range(self.N):
                for j in range(i+1, self.N):
                    self.model.addConstr(
                        d[k] >= self.tau[i][j] - self.M * (2 - self.x[i, k] - self.x[j, k]),
                        f"diam_{k}_{i}_{j}"
                    )
        
        # Funzione obiettivo
        obj = gp.quicksum(d[k] for k in range(self.K)) / self.K
        self.model.setObjective(obj, GRB.MINIMIZE)
    
    def solve(self, time_limit=300):
        """Risolvi il modello con parametri di ottimizzazione"""
        self.model.setParam('TimeLimit', time_limit)
        self.model.optimize()
        
    def get_clusters(self):
        """Estrai i cluster dalla soluzione"""
        clusters = {}
        if self.model.status == GRB.OPTIMAL:
            for k in range(self.K):
                clusters[k] = [i for i in range(self.N) if self.x[i, k].X > 0.5]
        return clusters