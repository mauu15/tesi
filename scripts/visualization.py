import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


output_dir = os.path.join(BASE_DIR, "imgs")
kmedoids_dir = os.path.join(output_dir, "kmedoids")

# Crea le cartelle se non esistono
for folder in [output_dir, kmedoids_dir]:
    os.makedirs(folder, exist_ok=True)

def plot_clusters(points, clusters, k, variant_name, d_i, s, medoid_indices=None, output_dir=None):
    """
    Plotta i punti in un grafico 2D colorati in base al cluster di appartenenza.

    Parameters
    ----------
    points : np.ndarray
        Array di shape (n_samples, 2) contenente le coordinate dei punti.
    clusters : dict
        Dizionario contenente gli indici dei punti per ogni cluster.
    medoid_indices : list or dict, optional
        Lista di indici dei medoidi. Se è un dizionario, i medoidi saranno ordinati
        in base alle chiavi.
    filename : str, optional
        Nome del file in cui salvare l'immagine.
    output_dir : str, optional
        Percorso della cartella in cui salvare l'immagine.

    """
    plt.figure(figsize=(8, 6))


    # Creazione dell'array di etichette per ogni punto
    labels = np.empty(points.shape[0], dtype=int)
    for cluster_id, indices in clusters.items():
        for i in indices:
            labels[i] = cluster_id

    # Plotta tutti i punti con un'unica chiamata a scatter
    plt.scatter(points[:, 0], points[:, 1], c=labels, cmap='viridis', s=50)
    
    # Se sono specificati i medoid, plottali
    if medoid_indices is not None:
        if isinstance(medoid_indices, dict):
            medoid_indices = [medoid_indices[k] for k in sorted(medoid_indices.keys())]
        elif isinstance(medoid_indices, list):
            medoid_indices = medoid_indices
        medoid_indices = np.array(medoid_indices, dtype=int)
        medoid_points = points[medoid_indices]
        plt.scatter(medoid_points[:, 0], medoid_points[:, 1],
                    color='red', marker='X', s=90, linewidths=0.8)
    
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Clustering")
    
    # Genera i dummy handle per comporre la voce "Pazienti"
    unique_clusters = sorted(clusters.keys())
    colors = plt.cm.viridis(np.linspace(0, 1, len(unique_clusters)))
    cluster_handles = tuple(
        Line2D([], [], marker='o', color=color, linestyle='', markersize=6)
        for color in colors
    )

    medoid_handle = Line2D([], [], marker='X', color='red', linestyle='',
                           markersize=8, markeredgewidth=1)
    
    # Crea la legenda che abbia due voci:
    # 1) Una tupla composta dai marker dei pazienti (cluster)
    # 2) Il marker per i medoidi
    plt.legend(
        [cluster_handles, medoid_handle],
        ["Pazienti", "Medoidi"],
        handler_map={tuple: HandlerTuple(ndivide=len(cluster_handles))}
    )
    
    plt.show()

    from utils import RESULTS_DIR
    if output_dir is None:
        output_dir = RESULTS_DIR
    output_dir = os.path.join(output_dir, f"variant_{variant_name}", f"day_{d_i}", f"session_{s}" ,"clusters_visualization")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"cluster_k{k}.png"
    filepath = os.path.join(output_dir, filename)
    
    plt.savefig(filepath, dpi=300)
    print(f"Immagine salvata in: {filepath}")
    
    plt.close()