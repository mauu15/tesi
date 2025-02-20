import numpy as np
import os
from sklearn.datasets import make_blobs
import matplotlib.pyplot as plt
from mip_clustering import MIPClustering
from visualization import plot_mip_clusters, kmeans_dir, minimax_dir, BASE_DIR

# -------------------------------
# Generazione dei dati sintetici
# -------------------------------
# Utilizziamo make_blobs per creare un dataset di 100 punti distribuiti su 2 dimensioni
# con 3 centri (cluster) e una deviazione standard elevata (cluster_std=4.0)
n_samples = 100
n_clusters = 3
X, _ = make_blobs(n_samples=n_samples, n_features=2, centers=n_clusters, random_state=42, cluster_std=4.0)

# Visualizzazione dei dati originali
plt.scatter(X[:, 0], X[:, 1], s=10)
plt.title('Dati Originali')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
original_img_path = os.path.join(BASE_DIR, "imgs", "original_data.png")
plt.savefig(original_img_path, dpi=300)
print(f"Immagine salvata in: {original_img_path}")
plt.show()

# ----------------------------------------------
# Test dei modelli MIP per diversi valori di K
# ----------------------------------------------
for K in [2, 3, 4]:
    print(f"\n--- Risoluzione con K={K} ---")
    
    # Creazione dell'istanza del modello MIPClustering.
    # L'oggetto riceve il dataset X e il numero di cluster desiderato K.
    model = MIPClustering(X, K)
    
    # ----------------------------------------
    # Modello K-Means MIP
    # ----------------------------------------
    # Il metodo create_kmeans_model() costruisce il modello MIP basato sulla formulazione
    # K-Means, che minimizza la somma pesata delle distanze tra i punti e il centroide assegnato.
    model.create_kmeans_model()
    
    # Risoluzione del modello con un limite temporale di 60 secondi.
    model.solve(time_limit=60)
    
    # Estrazione dei cluster ottenuti dalla soluzione.
    clusters = model.get_clusters()
    print(f"K-Means - Cluster trovati: {len(clusters)}")
    # Salvataggio dell'immagine con il plot dei cluster ottenuti dal modello K-Means MIP
    plot_mip_clusters(X, clusters, filename=f'kmeans_clusters_K{K}.png', output_dir=kmeans_dir)
    
    # ----------------------------------------
    # Modello Minimax MIP
    # ----------------------------------------
    # Il metodo create_minimax_model() costruisce il modello MIP secondo la formulazione Minimax,
    # che minimizza il diametro massimo (la massima distanza intra-cluster) per ottenere cluster più compatti.
    model.create_minimax_model()
    model.solve(time_limit=60)
    
    # Estrazione e visualizzazione dei cluster ottenuti con l'approccio Minimax.
    clusters = model.get_clusters()
    print(f"Minimax - Cluster trovati: {len(clusters)}")
    # Salvataggio dell'immagine con il plot dei cluster ottenuti dal modello Minimax MIP
    plot_mip_clusters(X, clusters, filename=f'minimax_clusters_K{K}.png', output_dir=minimax_dir)
