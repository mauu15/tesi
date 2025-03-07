import numpy as np
import os
from sklearn.datasets import make_blobs
import matplotlib.pyplot as plt
from mip_clustering import MIPClustering
from visualization import plot_clusters, kmedoids_dir, minimax_dir, BASE_DIR

# -------------------------------
# Generazione dei dati sintetici
# -------------------------------

n_samples = 300 # Numero di punti da generare
n_clusters = 4 # Numero di cluster

# Dati
# n_features=2: due dimensioni
# centers=n_clusters: numero di cluster
# random_state=42: seed per la riproducibilità
# cluster_std=4.0: deviazione standard dei cluster, maggiore significa cluster più dispersi
X, _ = make_blobs(n_samples=n_samples, n_features=2, centers=n_clusters, random_state=42, cluster_std=4.0)

# Visualizzazione dei dati originali
plt.scatter(X[:, 0], X[:, 1], s=10) # s=10: dimensione dei punti, 10 pixel
plt.title('Dati Originali')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
original_img_path = os.path.join(BASE_DIR, "imgs", "original_data.png")
plt.savefig(original_img_path, dpi=400)
print(f"Immagine salvata in: {original_img_path}")
plt.show()

# ----------------------------------------------
# Test dei modelli MIP per diversi valori di K
# ----------------------------------------------
for K in [2, 3, 4, 5]:
    print(f"\n--- Risoluzione con K={K} ---")
    
    # Creazione dell'istanza del modello MIPClustering.
    # L'oggetto riceve il dataset X e il numero di cluster desiderato K.
    model = MIPClustering(X, K)
    
    # ----------------------------------------
    # Modello K-Means MIP
    # ----------------------------------------
    # Il metodo create_kmeans_model() costruisce il modello MIP basato sulla formulazione
    # K-Means, che minimizza la somma pesata delle distanze tra i punti e il centroide assegnato.
    model.create_kmedoids_model()
    
    # Risoluzione del modello con un limite temporale di 60 secondi.
    model.solve(time_limit=6000)
    
    # Estrazione dei cluster ottenuti dalla soluzione.
    clusters = model.get_clusters()

    medoid_indices = model.get_medoids()

    print(f"K-Means - Cluster trovati: {len(clusters)}")
    # Salvataggio dell'immagine con il plot dei cluster ottenuti dal modello K-Medoids MIP
    plot_clusters(X, clusters, medoid_indices=medoid_indices, filename=f'kmedoids_clusters_K{K}.png', output_dir=kmedoids_dir)
    






















    # ----------------------------------------
    # Modello Minimax MIP
    # ----------------------------------------
    # Il metodo create_minimax_model() costruisce il modello MIP secondo la formulazione Minimax,
    # che minimizza il diametro massimo (la massima distanza intra-cluster) per ottenere cluster più compatti.
    # model.create_minimax_model()
    # model.solve(time_limit=6000)
    
    # # Estrazione e visualizzazione dei cluster ottenuti con l'approccio Minimax.
    # clusters = model.get_clusters()
    # print(f"Minimax - Cluster trovati: {len(clusters)}")
    # # Salvataggio dell'immagine con il plot dei cluster ottenuti dal modello Minimax MIP
    # plot_clusters(X, clusters, filename=f'minimax_clusters_K{K}.png', output_dir=minimax_dir)

    # # ----------------------------------------
    # # Modello K-Means con distanza pesata
    # # ----------------------------------------
    # # Creazione di pesi casuali per i punti del dataset.
    # # I pesi sono utilizzati per ponderare le distanze tra i punti e i centroidi

    # weights = np.random.uniform(0.5, 1.0, size=X.shape[0])


    # K = 3 # Numero di cluster
    # print(f"\n--- Risoluzione pesata con K={K} ---")
    # model_weighted = MIPClustering(X, K)
    # model_weighted.create_weighted_kmeans_model(weights)
    # model_weighted.solve(time_limit=6000)
    # clusters_weighted = model_weighted.get_clusters()
    
    # Salva l'immagine con il plot dei cluster ottenuti dal modello K-Means pesato
    #plot_clusters(X, clusters_weighted, filename=f'weighted_kmeans_clusters_K{K}.png', output_dir=kmedoids_dir)
