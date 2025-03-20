import gurobipy as gp
from gurobipy import GRB, quicksum
import numpy as np
from scipy.spatial import distance_matrix

class MIPClustering:
    def __init__(self, P, K, tau, w):
        """
        Inizializza l'istanza per il clustering MIP.
        
        Parametri:
        - patients: array numpy contenente i progetti da clusterizzare.
        - K: numero di cluster desiderato.
        - tau: matrice delle distanze tra i punti (tempi di viaggio)
        - w: pesi per ogni paziente in base a quante richieste hanno

        """

        self.P = P
        self.K = K                # Numero di cluster
        self.tau = tau

        self.model = gp.Model("k_medoids")
        self.x = None      # Variabili di assegnazione dei punti ai cluster
        self.y = None      # Variabili che indicano il centroide in ogni cluster (solo per K-Means)
        self.w = w         # Pesi per la funzione obiettivo
   

    def solve(self, time_limit=100, n_threads=8):
        """
        Risolve il modello MIP impostato (sia per K-Means)
        impostando un limite temporale per la risoluzione.
        
        Parametri:
        - time_limit: tempo massimo in secondi per la risoluzione del modello.
        """
        # Variabili di assegnazione: x[i,j] = 1 se il punto i è assegnato al medoid j
        self.x = self.model.addVars(self.P, self.P, vtype=GRB.BINARY, name="x")
        # Variabili che indicano se il punto j è scelto come medoid
        self.y = self.model.addVars(self.P, vtype=GRB.BINARY, name="y")
        

        # Vincolo 1: ogni punto deve essere assegnato a un unico medoid
        self.model.addConstrs(
            (quicksum(self.x[i, j] for j in self.P) == 1 for i in self.P),
            name="assignment"
        )
        
        # Vincolo 2: esattamente K medoids
        self.model.addConstr(
            quicksum(self.y[j] for j in self.P) == self.K,
            name="k_clusters"
        )
        

        # Vincolo 3: un punto i può essere assegnato a j solo se j è scelto come medoid
        self.model.addConstrs(
            (self.x[i, j] <= self.y[j] for i in self.P for j in self.P),
            name="link"
        )
        

        # Obiettivo: minimizzare la somma delle distanze tra i punti e il loro medoid assegnato
        # Poiché self.tau contiene già le distanze, basta usarlo direttamente.
        self.model.setObjective(
            quicksum(self.tau[i, j]*self.x[i, j]*self.w[i]*self.w[j] for i in self.P for j in self.P),
            GRB.MINIMIZE
        )
        
        self.model.setParam('TimeLimit', time_limit)
        self.model.setParam('Threads', n_threads)
        self.model.optimize()
        return True if self.model.status == GRB.OPTIMAL else False
    


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
            ones = [j for j in self.P if self.y[j].X > 0.5]
            for k in range(self.K):
                medoids[k] = ones[k]
                
            for k in range(self.K):
                # Se la variabile x[i,k] è maggiore di 0.5 (dato che è binaria) il punto i è assegnato a cluster k.
                clusters[k] = [i for i in self.P if self.x[i, medoids[k]].X > 0.5]

        return clusters


    def get_medoids(self):
        """
        Estrae gli indici dei medoid dalla soluzione ottimale.
        Ritorna:
        - Una lista degli indici dei punti che sono medoid.
        """
        medoids = [j for j in self.P if self.y[j].X > 0.5]
        return medoids
    

    def get_cluster_labels(self) -> list:
        """
        Estrae le etichette di cluster per ogni punto, in base alla soluzione
        del modello K-Medoids. Per ogni punto i, l'etichetta è l'indice j per cui
        la variabile x[i,j] è pari a 1.
        
        :return: Una lista di lunghezza N, dove l'elemento in posizione i è il cluster_id
                (l'indice del medoid assegnato) per il punto i.
        """
        
        labels = [] # Lista per i cluster, -1 indica nessuna assegnazione.
        for i in self.P:
            for j in self.P:
                
                if self.x[i, j].X > 0.5: 
                    labels.append(j)
                    break
        return labels