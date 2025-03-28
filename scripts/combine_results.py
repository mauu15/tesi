from utils import RESULTS_DIR
import os
import pandas as pd

def combine_results():
    """
    Combina i risultati di ogni variante in un unico CSV.

    Per ogni cartella in RESULTS_DIR/results che inizia per "variant_",
    legge:
      - il file parameters.txt in RESULTS_DIR/results/variant_<variant_name>,
        dove parameters.txt contiene:
            epsilon: <valore>
            down_time_true: <valore>
            multiplier: <valore>
      - il file global_statistics_<variant_name>.csv in 
        RESULTS_DIR/results/variant_<variant_name>,
        dal quale vengono estratte le colonne: 
            Total Cost, Routing Cost, Overtime Cost, Occupation Ratio

    Il CSV finale avrà le colonne:
      Variant,epsilon,down_time_true,multiplier,Total Cost,Routing Cost,Overtime Cost,Occupation Ratio
    e viene salvato in RESULTS_DIR/combined_results2.csv.
    """
    combined_results = []
    
    # Definisce il percorso della cartella "results"
    results_parent = os.path.join(RESULTS_DIR)
    if not os.path.exists(results_parent):
        print(f"Cartella {results_parent} non trovata.")
        return

    # Lista e ordina alfabeticamente le varianti trovate nella cartella "results"
    variant_dirs = []
    for entry in os.listdir(results_parent):
        variant_dir_path = os.path.join(results_parent, entry)
        if os.path.isdir(variant_dir_path) and entry.startswith("variant_"):
            # Estrae il nome della variante
            variant = entry.split("variant_")[-1]
            variant_dirs.append((variant, variant_dir_path))
    variant_dirs.sort(key=lambda x: x[0])
    
    for variant, variant_dir_path in variant_dirs:
        # Leggi parameters.txt
        params_file = os.path.join(variant_dir_path, "parameters.txt")
        if not os.path.exists(params_file):
            print(f"File parameters.txt non trovato in {variant_dir_path}.")
            continue

        params = {}
        with open(params_file, "r") as pf:
            for line in pf:
                if ":" in line:
                    key, value = line.split(":", 1)
                    params[key.strip()] = value.strip()

        # Leggi global_statistics_<variant>.csv
        stats_file = os.path.join(variant_dir_path, f"global_statistics_{variant}.csv")
        if not os.path.exists(stats_file):
            print(f"File {stats_file} non trovato.")
            continue

        try:
            stats_df = pd.read_csv(stats_file)
        except Exception as e:
            print(f"Errore nella lettura di {stats_file}: {e}")
            continue

        if stats_df.empty:
            print(f"Il file {stats_file} è vuoto.")
            continue

        stats = stats_df.iloc[0].to_dict()

        result_row = {
            "Variant": variant,
            "epsilon": params.get("epsilon", ""),
            "down_time_true": params.get("down_time_true", ""),
            "multiplier": params.get("multiplier", ""),
            "Total Waiting Time": stats.get("Total Waiting Time", ""),
            "Average Waiting Time": stats.get("Average Waiting Time", ""),
            "Total Cost": stats.get("Total Cost", ""),
            "Routing Cost": stats.get("Routing Cost", ""),
            "Overtime Cost": stats.get("Overtime Cost", ""),
            "Occupation Ratio": stats.get("Occupation Ratio", "")
        }
        combined_results.append(result_row)
    
    if combined_results:
        combined_df = pd.DataFrame(combined_results)
        output_file = os.path.join(RESULTS_DIR, "combined_results2.csv")
        combined_df.to_csv(output_file, index=False)
        print(f"File combinato salvato in {output_file}")
    else:
        print("Nessun risultato da combinare.")

if __name__ == "__main__":
    combine_results()
