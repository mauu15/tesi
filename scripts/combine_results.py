from utils import RESULTS_DIR
import os

from utils import RESULTS_DIR
import os
import pandas as pd

def combine_results(variant_names):
    """
    Combina i risultati di ogni variante in un unico CSV.
    
    Per ogni variante in variant_names, legge:
      - il file parameters.txt in RESULT_DIR/variant_{variant},
        dove parameters.txt contiene:
            epsilon: <valore>
            down_time_true: <valore>
            multiplier: <valore>
      - il file global_statistics_{variant}.csv in RESULT_DIR/variant_{variant},
        dal quale vengono estratte le colonne: 
            Total Cost, Routing Cost, Overtime Cost, Occupation Ratio
    
    Il CSV finale avrà le colonne:
      Variant,epsilon,down_time_true,multiplier,Total Cost,Routing Cost,Overtime Cost,Occupation Ratio
    e viene salvato in RESULT_DIR/combined_results.csv.
    """
    combined_results = []
    
    for variant in variant_names:
        variant_dir = os.path.join(RESULTS_DIR, f"variant_{variant}")
        
        # Leggi parameters.txt
        params_file = os.path.join(variant_dir, "parameters.txt")
        if not os.path.exists(params_file):
            print(f"File parameters.txt non trovato in {variant_dir}.")
            continue
        
        params = {}
        with open(params_file, "r") as pf:
            for line in pf:
                if ":" in line:
                    key, value = line.split(":", 1)
                    params[key.strip()] = value.strip()
        
        # Leggi global_statistics_{variant}.csv
        stats_file = os.path.join(variant_dir, f"global_statistics_{variant}.csv")
        if not os.path.exists(stats_file):
            print(f"File {stats_file} non trovato.")
            continue
        
        try:
            stats_df = pd.read_csv(stats_file)
        except Exception as e:
            print(f"Errore nella lettura di {stats_file}: {e}")
            continue
        
        # Assumiamo che il CSV contenga una sola riga
        if stats_df.empty:
            print(f"Il file {stats_file} è vuoto.")
            continue
        stats = stats_df.iloc[0].to_dict()
        
        result_row = {
            "Variant": variant,
            "lambda": params.get("epsilon", ""),
            "down_time_true": params.get("down_time_true", ""),
            "multiplier": params.get("multiplier", ""),
            "Waiting Time": stats.get("Waiting Time", ""),
            "Total Cost": stats.get("Total Cost", ""),
            "Routing Cost": stats.get("Routing Cost", ""),
            "Overtime Cost": stats.get("Overtime Cost", ""),
            "Occupation Ratio": stats.get("Occupation Ratio", "")
        }
        combined_results.append(result_row)
    
    if combined_results:
        combined_df = pd.DataFrame(combined_results)
        output_file = os.path.join(RESULTS_DIR, "combined_results.csv")
        combined_df.to_csv(output_file, index=False)
        print(f"File combinato salvato in {output_file}")
    else:
        print("Nessun risultato da combinare.")

# Esempio di chiamata alla funzione (da richiamare alla fine del programma principale)
if __name__ == "__main__":
    # Sostituire con la lista delle variante desiderate, ad es. ["A", "B", "C"]
    variants = ["A"]
    combine_results(variants)