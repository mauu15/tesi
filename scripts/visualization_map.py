# -*- coding: utf-8 -*-
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple
from utils import RESULTS_DIR # Assicurati che questo import funzioni
import geopandas as gpd
import contextily as ctx
import warnings # Per silenziare eventuali warning di contextily

# Definizione di BASE_DIR (opzionale)
try:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    BASE_DIR = os.getcwd()

def plot_clusters_with_map(points_latlon, clusters, k, variant_name, d_i, s, medoid_indices=None):
    """
    Plotta i punti geolocalizzati su mappa OSM Mapnik (opacità 0.60),
    forzando un aspect ratio orizzontale per la vista mappa.
    Utilizza la palette 'Dark2'. Pallini cluster più grandi (s=80).
    Medoidi (X rosse) con bordo nero. Legenda interna. Salvataggio a 150 DPI.

    Parameters
    ----------
    points_latlon : np.ndarray
        Array (n_samples, 2) [latitude, longitude].
    clusters : dict
        Dizionario {cluster_id: [indices...]}.
    k : int
        Numero di cluster (per titolo).
    variant_name : str
        Nome variante.
    d_i : int or str
        Giorno.
    s : int or str
        Sessione.
    medoid_indices : list or np.ndarray, optional
        Indici dei medoidi.
    """
    print("Inizio plot con mappa...")

    # --- 1. Preparazione dei dati GeoDataFrame ---
    points_lonlat = points_latlon[:, [1, 0]]
    gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(points_lonlat[:, 0], points_lonlat[:, 1]),
        crs="EPSG:4326"
    )
    labels = np.full(len(gdf), -1, dtype=int)
    if not clusters:
        print("Attenzione: il dizionario 'clusters' è vuoto.")
    else:
        for cluster_id, indices in clusters.items():
            valid_indices = [idx for idx in indices if idx < len(labels)]
            indices_int = np.array(valid_indices, dtype=int)
            if len(indices_int) > 0:
                labels[indices_int] = cluster_id
    gdf['cluster'] = labels
    unique_clusters = sorted([cid for cid in gdf['cluster'].unique() if cid != -1])
    if not unique_clusters:
         print("Attenzione: Nessun cluster ID valido trovato nei dati.")

    # --- 2. Trasformazione delle coordinate ---
    print("Trasformazione coordinate in Web Mercator (EPSG:3857)...")
    gdf_wm = gdf.to_crs(epsg=3857)
    points_wm = np.array([(point.x, point.y) for point in gdf_wm.geometry])

    # --- 3. Plotting e Calcolo Limiti ---
    fig_width, fig_height = 12, 10
    figsize = (fig_width, fig_height)
    target_aspect = fig_width / fig_height

    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Palette raccomandata 'Dark2'
    custom_palette = [
        '#1b9e77', '#d95f02', '#7570b3', '#e7298a',
        '#66a61e', '#e6ab02', '#a6761d', '#666666'
    ]
    num_custom_colors = len(custom_palette)
    default_color = 'grey'
    color_map = {}

    # Gestione colore per k=1
    if len(unique_clusters) == 1:
        single_cluster_id = unique_clusters[0]
        visible_color = custom_palette[0]
        print(f"Rilevato k=1 (cluster ID: {single_cluster_id}), uso colore specifico: {visible_color}")
        color_map = {single_cluster_id: visible_color}
    elif len(unique_clusters) > 1:
        print(f"Uso la palette raccomandata 'Dark2' con {num_custom_colors} colori.")
        color_map = {cluster_id: custom_palette[i % num_custom_colors]
                     for i, cluster_id in enumerate(unique_clusters)}
        if len(unique_clusters) > num_custom_colors:
            print(f"Attenzione: Numero cluster ({len(unique_clusters)}) > {num_custom_colors} (colori palette), i colori si ripeteranno.")

    # Mappa i cluster ID ai colori
    point_colors = gdf_wm['cluster'].apply(lambda cid: color_map.get(cid, default_color))

    # Plotta punti (più grandi)
    print(f"Plotting punti...")
    # >>> CAMBIAMENTO: Aumentata dimensione 's' <<<
    scatter = ax.scatter(points_wm[:, 0], points_wm[:, 1],
                         color=point_colors,
                         s=100,               # Aumentata dimensione
                         alpha=0.85,
                         edgecolor='black',  # Bordo già presente
                         linewidth=0.5,      # Spessore bordo già presente
                         zorder=5)

    # Plotta medoidi (con bordo nero)
    medoid_points_wm = None
    if medoid_indices is not None:
        medoid_indices_arr = np.array(medoid_indices, dtype=int)
        valid_medoid_indices = medoid_indices_arr[medoid_indices_arr < len(points_wm)]
        if len(valid_medoid_indices) > 0:
            print("Plotting medoidi...")
            medoid_points_wm = points_wm[valid_medoid_indices]
            ax.scatter(medoid_points_wm[:, 0], medoid_points_wm[:, 1],
                       color='#FF0000', marker='X', s=160,
                       edgecolor='black', linewidths=1.0,
                       zorder=10)

    # Forza i limiti dell'asse
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    data_height = ymax - ymin
    data_width = xmax - xmin
    if data_height > 0 and data_width > 0:
        required_width = data_height * target_aspect
        if required_width > data_width:
            x_center = (xmin + xmax) / 2
            new_xmin = x_center - required_width / 2
            new_xmax = x_center + required_width / 2
            print(f"Forzatura limiti X: ({new_xmin:.2f}, {new_xmax:.2f}) per aspect ratio {target_aspect:.2f}")
            ax.set_xlim(new_xmin, new_xmax)
            ax.set_ylim(ymin, ymax)

    # --- 4. Aggiunta della mappa di sfondo ---
    print("Aggiunta basemap...")
    try:
        basemap_provider = ctx.providers.OpenStreetMap.Mapnik
        print(f"Uso provider basemap: {basemap_provider.name}")
        with warnings.catch_warnings():
             warnings.simplefilter("ignore", UserWarning)
             ctx.add_basemap(ax, crs=gdf_wm.crs.to_string(),
                            source=basemap_provider, zoom='auto')
        print("Basemap aggiunta con successo.")
        if ax.images:
             # >>> CAMBIAMENTO: Modificata opacità mappa <<<
             map_alpha_value = 0.60
             ax.images[-1].set_alpha(map_alpha_value)
             print(f"Opacità mappa impostata a: {map_alpha_value}")
        ax.set_aspect('equal', adjustable='box')
        print("Aspect ratio dell'asse impostato a 'equal'.")
    except Exception as e:
        print(f"Errore durante il download della basemap: {e}")
        print("Il plot verrà generato senza mappa di sfondo.")

    # --- 5. Titolo, Legenda e Stile ---
    ax.set_title(f"Clustering K={k} su Mappa (Variant: {variant_name}, Day: {d_i}, Session: {s})")
    ax.set_axis_off()

    # Crea maniglie legenda (aggiorna markersize se vuoi coerenza con i punti più grandi)
    handles = []
    labels_legend = []
    if unique_clusters and color_map:
        cluster_handles = tuple(
            Line2D([], [], marker='o', color=color_map[cluster_id], linestyle='',
                   # >>> POTREBBE SERVIRE AUMENTARE markersize qui se 8 è troppo piccolo rispetto a s=80 <<<
                   markersize=9, # Leggermente più grande anche nella legenda
                   alpha=0.85, markeredgecolor='black', markeredgewidth=0.5)
            for cluster_id in unique_clusters
        )
        if cluster_handles:
            handles.append(cluster_handles)
            labels_legend.append("Pazienti (Cluster)")
    # Maniglia medoidi (con bordo nero)
    if medoid_points_wm is not None:
         medoid_handle = Line2D([], [], marker='X', color='#FF0000', linestyle='',
                                markersize=9, markeredgecolor='black', markeredgewidth=1.0)
         handles.append(medoid_handle)
         labels_legend.append("Medoidi")

    if handles:
        ax.legend(handles, labels_legend,
                  handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
                  loc='upper right', frameon=True, framealpha=0.75, fontsize='medium')

    # --- 6. Salvataggio ---
    save_folder = os.path.join(RESULTS_DIR, f"variant_{variant_name}", f"day_{d_i}", f"session_{s}", "clusters_visualization_map")
    os.makedirs(save_folder, exist_ok=True)
    filename = f"cluster_map_k{k}.png"
    filepath = os.path.join(save_folder, filename)

    print(f"Salvataggio immagine in: {filepath}")
    try:
        # >>> CAMBIAMENTO: Modificato dpi <<<
        plt.savefig(filepath, dpi=150, bbox_inches='tight', pad_inches=0.1)
        print(f"Immagine salvata.")
    except Exception as e:
        print(f"Errore durante il salvataggio dell'immagine: {e}")
    finally:
        plt.close(fig)