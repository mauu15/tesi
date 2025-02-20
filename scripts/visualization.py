import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

# Gestione cartelle
output_dir = "imgs"
kmeans_dir = os.path.join(output_dir, "kmeans")
minimax_dir = os.path.join(output_dir, "minimax")

# Crea le cartelle se non esistono
for folder in [output_dir, kmeans_dir, minimax_dir]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def plot_clusters(X, k_values=[2, 3], labels_list=None, filename="kmeans_clusters.png", output_dir=kmeans_dir):
    """
    Visualizza i dati clusterizzati in 2D utilizzando PCA per la riduzione dimensionale.
    
    Parametri:
    - X: array di dati (ogni riga è un punto e ogni colonna una feature).
    - k_values: lista dei valori di K (numero di cluster) per i quali eseguire il clustering KMeans.
    - labels_list: (opzionale) lista di etichette di cluster già calcolate per ogni valore di K.
    - filename: nome del file per salvare l'immagine.
    
    Se labels_list non viene fornito, la funzione esegue il clustering KMeans per ogni K.
    """
    if X is None or len(X) == 0:
        print("Dati non validi per la visualizzazione.")
        return

    # Riduzione dimensionale: PCA per trasformare i dati in 2 componenti principali.
    pca = PCA(n_components=2)
    X_reduced = pca.fit_transform(X)

    # Creazione della figura con subplots per ciascun valore di K
    fig, axes = plt.subplots(1, len(k_values), figsize=(12, 6))

    # Loop su ogni valore di K per visualizzare i risultati del clustering
    for i, k in enumerate(k_values):
        if labels_list is None:
            # Esegue il clustering KMeans se non sono state fornite etichette pre-calcolate
            kmeans = KMeans(n_clusters=k, random_state=42)
            labels = kmeans.fit_predict(X)
        else:
            # Utilizza le etichette fornite dall'utente
            labels = labels_list[i]

        # Visualizza i dati ridotti, colorando ogni punto in base al cluster di appartenenza
        axes[i].scatter(X_reduced[:, 0], X_reduced[:, 1], c=labels, cmap='viridis')
        axes[i].set_title(f"KMeans Clustering K={k}")
        axes[i].set_xlabel("PCA Component 1")
        axes[i].set_ylabel("PCA Component 2")

    plt.tight_layout()
    # Salvataggio della figura in formato PNG ad alta risoluzione (300 dpi)
    plt.savefig(os.path.join(output_dir, filename), dpi=300)

def plot_mip_clusters(X, clusters, filename="mip_clusters.png", output_dir=minimax_dir):
    """
    Visualizza i dati clusterizzati in 2D utilizzando PCA per la riduzione dimensionale.
    
    Parametri:
    - X: array di dati (ogni riga è un punto e ogni colonna una feature).
    - clusters: dizionario che mappa l'ID del cluster ad una lista di indici dei punti appartenenti.
    - filename: nome del file per salvare l'immagine.
    
    La funzione crea una visualizzazione in cui ogni punto è colorato in base al cluster di appartenenza.
    """
    if X is None or len(X) == 0:
        print("Dati non validi per la visualizzazione.")
        return

    # Riduzione dimensionale tramite PCA a 2 componenti
    pca = PCA(n_components=2)
    X_reduced = pca.fit_transform(X)

    # Creazione dell'array delle etichette: ogni punto riceve il numero del cluster in cui è stato assegnato
    labels = np.zeros(X.shape[0])
    for k, indices in clusters.items():
        for idx in indices:
            labels[idx] = k

    # Visualizzazione con scatter plot e uso di una mappa colori (viridis)
    plt.scatter(X_reduced[:, 0], X_reduced[:, 1], c=labels, cmap='viridis')
    plt.title("MIP Clustering")
    plt.xlabel("PCA Component 1")
    plt.ylabel("PCA Component 2")
    plt.savefig(os.path.join(minimax_dir, filename), dpi=300)

    # Verifica se la directory esiste e creala se necessario
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    plt.savefig(os.path.join(output_dir, filename), dpi=300)

# -------------------------------
# Esempio di utilizzo delle funzioni
# -------------------------------
if __name__ == "__main__":
    # Genera 100 punti casuali in 2D per testare la visualizzazione
    X = np.random.rand(100, 2)

    # Visualizza il clustering ottenuto con KMeans per valori predefiniti di K
    plot_clusters(X)

    # Esempio di visualizzazione per clustering ottenuto con il modello MIP
    clusters_example = {0: [0, 1, 2], 1: [3, 4, 5], 2: [6, 7, 8]}
    plot_mip_clusters(X, clusters_example)
