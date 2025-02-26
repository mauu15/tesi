import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

# Definizione della cartella base del progetto.
# Poiché questo file si trova in "tesi/scripts", il BASE_DIR sarà "tesi"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gestione cartelle: le immagini saranno salvate in BASE_DIR/imgs
output_dir = os.path.join(BASE_DIR, "imgs")
kmedoids_dir = os.path.join(output_dir, "kmedoids")
minimax_dir = os.path.join(output_dir, "minimax")

# Crea le cartelle se non esistono
for folder in [output_dir, kmedoids_dir, minimax_dir]:
    os.makedirs(folder, exist_ok=True)

def plot_clusters(points, clusters, medoid_indices=None, filename=None, output_dir=None):
    
    labels = np.empty(points.shape[0], dtype=int)
    for cluster_id, indices in clusters.items():
        for i in indices:
            labels[i] = cluster_id

    plt.figure(figsize=(8, 6))
    plt.scatter(points[:, 0], points[:, 1], c=labels, cmap='viridis', label='Pazienti')
    if medoid_indices is not None:
        medoid_points = points[medoid_indices]
        plt.scatter(medoid_points[:, 0], medoid_points[:, 1], color='red', marker='D', s=100, label='Medoidi')
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Clustering")
    plt.legend()
    
    if filename is not None and output_dir is not None:
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300)
        print(f"Immagine salvata in: {filepath}")
    
    plt.show()