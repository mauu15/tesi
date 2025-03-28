# file con funzioni di utilità per la tesi

###############################################################################
# Funzioni di setup dei turni
###############################################################################

# POMERIGGIO
def set_operator_state_afternoon(operator):
    """
    Reimposta lo stato dell'operatore per il turno pomeridiano.
    - Se l'operatore ha lavorato dopo le 11:30 (worked_after_11:30am == True),
      il turno pomeridiano inizia alle 18:00 (1080 minuti).
    - Se l'operatore ha lavorato al mattino (worked_morning == True) ma non dopo le 11:30,
      il turno pomeridiano inizia alle 16:00 (960 minuti).
    - Se l'operatore non ha lavorato al mattino, inizia comunque alle 16:00 (960 minuti) 
      e con un turno di 5 ore (300 minuti disponibili).
    """
    if operator.get("worked_after_11:30am", False):
        operator["eo_start_afternoon"] = 1080
        operator["eo"] = 1080
        operator["ho"] = 240
    else:
        operator["eo_start_afternoon"] = 960
        operator["eo"] = 960
        operator["ho"] = 360

    operator["current_patient_id"] = 'h'
    operator["overtime_minutes"] = 0

# MATTINA
def set_operator_state_morning(operator):
    """
    Reimposta lo stato dell'operatore per il turno mattutino.
    Il turno mattutino inizia alle 7:00 (420 minuti).
    """
    operator["eo"] = 420
    operator["ho"] = 330
    operator["current_patient_id"] = 'h'
    operator["worked_after_11:30am"] = False
    operator["overtime_minutes"] = 0

def update_operator_shift_counts(operators):
    """
    Calcola o aggiorna single_shift_requests e double_shift_requests
    per ogni operatore in base alle informazioni correnti
    (e.g. operator['worked_morning'], operator['worked_after_11:30am'], ecc.).
    """
    for op in operators:
        op['single_shift_requests'] = 0
        op['double_shift_requests'] = 0
        for d in range(7):
            req_o = [req  for (req, _) in op['Lo'] if req['day'] == d]
            o_worked_morning = any(parse_time_to_minutes(req['min_time_begin']) < 12*60 + 30 for req in req_o)
            o_worked_afternoon = any(parse_time_to_minutes(req['min_time_begin']) >= 16*60 for req in req_o)
            if o_worked_morning or o_worked_afternoon:
                if o_worked_morning and o_worked_afternoon:
                    op['double_shift_requests'] += 1
                else:
                    op['single_shift_requests'] += 1
            

def update_operator_priority(operators, epsilon):
    """
    Aggiorna SSRo, DSRo e priority in base ai campi single_shift_requests e double_shift_requests.
    """
    for op in operators:
        if op["Ho"] == 0:
            op['SSRo'] = 0
            op['DSRo'] = 0
            op['priority'] = 0
            continue
        
        op['SSRo'] = (op['single_shift_requests'] * 5.0) / op["Ho"]
        op['DSRo'] = (op.get('double_shift_requests', 0) * 7.5) / op["Ho"]
        op['priority'] = epsilon * op['SSRo'] + (1 - epsilon) * op['DSRo']  


##############################################################
# Funzioni per la manipolazione di date e orari
##############################################################

def parse_time_to_minutes(time_value):
    """
    Converte un orario espresso nel formato H.MM (es. "15.55" per 15:55)
    in minuti. Ad esempio: "15.55" → 15*60 + 55 = 955 minuti.
    Se il valore non contiene il punto, lo interpreta come ore e lo converte in minuti.
    """
    # s = str(time_value)
    # if '.' in s:
    #     parts = s.split('.')
    #     hour = int(parts[0])
    #     minute = int(parts[1])
    #     return hour * 60 + minute
    # else:
    #     return int(float(s) * 60)

    import numpy as np
    time = float(time_value)
    hours = int(time)
    minutes = hours * 60 + np.round((time - hours) * 100, 0)

    return int(minutes)



def parse_minutes_to_hours(time_value):
    """
    Converte un valore espresso in minuti in ore e minuti.
    Ad esempio: 955 minuti → "15.55".
    """
    total = int(round(time_value))
    hours = total // 60
    minutes = total % 60
    
    return f"{hours}:{minutes:02d}"

##############################################################
# Funzioni per il report dei risultati
##############################################################

import os
RESULTS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "results")

def display_assignments(assignments, operators):
    """"
    Mostra i risultati dell'assegnazione delle richieste agli operatori."
    """
    import pandas as pd
    data = []
    for op_id, req_list in assignments.items():
        data.append({
            "Operator ID": op_id,
            "Name": next(op["name"] for op in operators if op["id"] == op_id),
            "Surname": next(op["surname"] for op in operators if op["id"] == op_id),
            "Num Requests": len(req_list),
            "Request IDs": ", ".join(req_list)
        })
    df = pd.DataFrame(data)
    return df

def display_assignments_with_shifts(operators):
    """
    Costruisce un DataFrame che mostra, per ciascun operatore:
    - Quante richieste ha fatto al mattino
    - Quante richieste ha fatto al pomeriggio
    - Il totale di minuti (o ore) lavorati in settimana
    - L'elenco di ID richieste mattina/pomeriggio
    """

    import pandas as pd
    data = []
    for op in operators:
        overtime = max(0, op["wo"] - op["Ho"])
        data.append({
            "Operator ID": op["id"],
            "Name": op["name"],
            "Surname": op["surname"],
            "Assigned Requests": ", ".join(str(x[0]["id"]) for x in op["Lo"]),
            "Num Requests": len(op["Lo"]),
            "Total Hours Worked": parse_minutes_to_hours(op["wo"]),
            "Max Weekly Hours": parse_minutes_to_hours(op["Ho"]),
            "Road Time": parse_minutes_to_hours(op["road_time"]),
            "Waiting Time": parse_minutes_to_hours(op["do"]),
            "Overtime": parse_minutes_to_hours(overtime) if overtime else "No overtime",
        })
    return pd.DataFrame(data)

def display_session_statistics(operators, baseline_operators):
    """
    Calcola le statistiche globali dai dati dei singoli operatori:
      - Assigned Requests: somma delle richieste assegnate (lunghezza di op["Lo"])
      - Unsatisfied Requests: differenza tra il totale delle richieste in ingresso e quelle assegnate
      - Total Waiting Time: somma totale del waiting time (in formato H:MM)
      - Total Road Time: somma dei tempi di spostamento
      - Average Waiting Time: media dei waiting time degli operatori
      - Average Road Time: media dei road time degli operatori
    """
    import pandas as pd

    # Calcola il numero di richieste assegnate all'inizio e alla fine della sessione
    assigned_requests_end = sum(len(op["Lo"]) for op in operators)
    assigned_requests_start = sum(len(op["Lo"]) for op in baseline_operators)

    # Calcola il delta delle richieste assegnate
    assigned_requests_delta = assigned_requests_end - assigned_requests_start

    assigned_requests = sum(len(op["Lo"]) for op in operators)
    total_waiting = sum(op["do"] for op in operators)
    total_road = sum(op["road_time"] for op in operators)
    avg_waiting = total_waiting / len(operators) if operators else 0
    avg_road = total_road / len(operators) if operators else 0
    overtime_minutes = sum(op["overtime_minutes"] for op in operators)

    
    # Calcola il totale delle ore lavorate
    total_hours_worked = sum(op["wo"] for op in operators)

    stats = {
        "Assigned Requests": assigned_requests_delta,
        "Total Waiting Time": parse_minutes_to_hours(total_waiting),
        "Total Road Time": parse_minutes_to_hours(total_road),
        "Average Waiting Time": parse_minutes_to_hours(avg_waiting),
        "Average Road Time": parse_minutes_to_hours(avg_road),
        "Total Overtime": parse_minutes_to_hours(overtime_minutes),
        "Total Hours Worked": parse_minutes_to_hours(total_hours_worked)
    }
    return pd.DataFrame([stats])


def display_global_statistics(operators, total_cost, total_overtime_cost, total_routing_cost):
    """
    Calcola le statistiche globali dai dati dei singoli operatori:
      - Assigned Requests: somma delle richieste assegnate (lunghezza di op["Lo"])
      - Unsatisfied Requests: differenza tra il totale delle richieste in ingresso e quelle assegnate
      - Total Waiting Time: somma totale del waiting time (in formato H:MM)
      - Total Road Time: somma dei tempi di spostamento
      - Average Waiting Time: media dei waiting time degli operatori
      - Average Road Time: media dei road time degli operatori
    """
    import pandas as pd
    assigned_requests = sum(len(op["Lo"]) for op in operators)
    total_waiting = sum(op["do"] for op in operators)
    total_road = sum(op["road_time"] for op in operators)
    avg_waiting = total_waiting / len(operators) if operators else 0
    avg_road = total_road / len(operators) if operators else 0

    # Calcola l'overtime totale
    total_overtime = sum(max(0, op["wo"] - op["Ho"]) for op in operators)

    # Calcola il totale delle ore lavorate
    total_hours_worked = sum(op["wo"] for op in operators)

    stats = {
        "Assigned Requests": assigned_requests,
        "Total Waiting Time": parse_minutes_to_hours(total_waiting),
        "Total Road Time": parse_minutes_to_hours(total_road),
        "Average Waiting Time": parse_minutes_to_hours(avg_waiting),
        "Average Road Time": parse_minutes_to_hours(avg_road),
        "Total Cost": round(total_cost, 2),
        "Routing Cost": round(total_routing_cost, 2),
        "Overtime Cost": round(total_overtime_cost, 2),
        "Total Overtime": parse_minutes_to_hours(total_overtime),
        "Total Hours Worked": parse_minutes_to_hours(total_hours_worked)
    }
    return pd.DataFrame([stats])


def save_statistics(variant_name, day, session, k, cost_ds, total_cost, global_stats_df, assignments_df):
    """
    Salva le statistiche nella seguente struttura di cartelle:
    results/variant_{variant_name}/day_{day}/session_{session}/k_{k}/
    Include un file JSON (stats.json) e due file CSV:
      - global_statistics.csv (generato con display_global_statistics)
      - assignments.csv (generato con display_assignments_with_shifts)
    """
    import os, json, shutil
    folder_path = os.path.join(RESULTS_DIR, f"variant_{variant_name}", f"day_{day}", f"session_{session}", f"k_{k}")
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    os.makedirs(folder_path, exist_ok=True)
    
    cost_ds_str = {f"{key[0]}_{key[1]}": value for key, value in cost_ds.items()}

    
    
    data = {
        "variant": variant_name,
        "day": day,
        "session": session,
        "k": k,
        "cost_ds": cost_ds_str,
        "total_cost": round(total_cost, 2)
    }

    out_file = os.path.join(folder_path, f"stats_D{day}_S{session}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    
    # Salvataggio global statistics in CSV
    global_csv = os.path.join(folder_path, f"statistics_D{day}_S{session}.csv")
    global_stats_df.to_csv(global_csv, index=False)
    
    # Salvataggio assignments (con turni) in CSV
    assignments_csv = os.path.join(folder_path, f"assignments_D{day}_S{session}.csv")
    assignments_df.to_csv(assignments_csv, index=False)


def save_global_statistics(operators, total_cost, total_overtime_cost, total_routing_cost, output_dir=RESULTS_DIR):
    os.makedirs(output_dir, exist_ok=True)
    global_stats_df = display_global_statistics(operators, total_cost, total_overtime_cost, total_routing_cost)
    save_path = os.path.join(output_dir, "global_statistics.csv")
    global_stats_df.to_csv(save_path, index=False)
    print(f"Global statistics saved to {save_path}")

def save_global_assignments(operators, output_dir=RESULTS_DIR):
    os.makedirs(output_dir, exist_ok=True)
    assignments_df = display_assignments_with_shifts(operators)
    save_path = os.path.join(output_dir, "global_assignments.csv")
    assignments_df.to_csv(save_path, index=False)
    print(f"Global assignments saved to {save_path}")


def display_session_deltas(operators, baseline_operators):
    """
    Costruisce un DataFrame che mostra, per ciascun operatore, i delta ottenuti dalla
    differenza tra lo stato attuale e quello di baseline della sessione.
    
    Le colonne sono:
      - Operator ID
      - Assigned Requests (delta): differenza nel numero di richieste assegnate
      - Additional Working Time: incremento dei minuti lavorati (puoi formattarli in ore:minuti se preferisci)
      - Additional Waiting Time: incremento dei minuti di attesa
      - Additional Road Time: incremento dei minuti di spostamento
    """
    import pandas as pd
    session_deltas = []
    for op_current, op_baseline in zip(operators, baseline_operators):
        baseline_ids = {req[0]["id"] for req in op_baseline["Lo"]}
        new_assigned = [req for req in op_current["Lo"] if req[0]["id"] not in baseline_ids]
        delta = {
            "Operator ID": op_current["id"],
            "Name": op_current["name"],
            "Surname": op_current["surname"],
            "Assigned Requests": ", ".join(str(req[0]["id"]) for req in new_assigned),
            "Num Requests": len(new_assigned),
            "Working Time": parse_minutes_to_hours(op_current["wo"] - op_baseline["wo"]),
            "Waiting Time": parse_minutes_to_hours(op_current["do"] - op_baseline["do"]),
            "Road Time": parse_minutes_to_hours(op_current["road_time"] - op_baseline["road_time"])
        }
        session_deltas.append(delta)
    return pd.DataFrame(session_deltas)

def time_str_to_minutes(time_str: str) -> int:
    """
    Converte una stringa che rappresenta un orario nel formato "H:MM" o "H.MM" in minuti.
    Se la stringa è "No overtime", restituisce 0.
    
    Esempi:
      "15:55" → 15*60 + 55 = 955 minuti
      "15.55" → 955 minuti
      "15"   → 15 ore → 900 minuti
      
    :param time_str: Stringa con il formato orario
    :return: Il totale dei minuti
    """
    if time_str == "No overtime":
        return 0

    if ":" in time_str:
        parts = time_str.split(":")
    elif "." in time_str:
        parts = time_str.split(".")
    else:
        try:
            hours = int(time_str)
            return hours * 60
        except ValueError:
            raise ValueError(f"Formato orario non riconosciuto: {time_str}")
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
    except (IndexError, ValueError) as e:
        raise ValueError(f"Formato orario non valido: {time_str}") from e

    return hours * 60 + minutes

def plot_time_distributions(df, variant_name, output_dir=RESULTS_DIR, show_plot=False):
    """
    Crea e salva 3 box plot separati:
      1. 'Overtime_minutes'
      2. 'Waiting Time_minutes'
      3. 'Road Time_minutes'
    Ogni grafico viene salvato nella cartella della variante con l'asse x etichettato rispettivamente:
      "Overtime", "Waiting Time" e "Road Time"
    Se show_plot è True, il grafico viene mostrato a schermo.
    """
    import matplotlib.pyplot as plt
    import os

    # Assicurati che le colonne *minutes siano presenti nel DataFrame;
    # se non ci sono ma ci sono le colonne originali, le creiamo:
    if 'Overtime_minutes' not in df.columns and 'Overtime' in df.columns:
        df['Overtime_minutes'] = df['Overtime'].apply(time_str_to_minutes)
    if 'Waiting Time_minutes' not in df.columns and 'Waiting Time' in df.columns:
        df['Waiting Time_minutes'] = df['Waiting Time'].apply(time_str_to_minutes)
    if 'Road Time_minutes' not in df.columns and 'Road Time' in df.columns:
        df['Road Time_minutes'] = df['Road Time'].apply(time_str_to_minutes)

    # Crea la cartella della variante se non esiste
    variant_dir = os.path.join(output_dir, f"variant_{variant_name}")
    os.makedirs(variant_dir, exist_ok=True)

    # Lista di tuple (nome_colonna, nome_file, etichetta per l'asse x)
    time_plots = [
        ("Overtime_minutes",      f"distribution_boxplot_overtime_variant{variant_name}.png", "Overtime"),
        ("Waiting Time_minutes",  f"distribution_boxplot_waiting_variant{variant_name}.png",  "Waiting Time"),
        ("Road Time_minutes",     f"distribution_boxplot_road_variant{variant_name}.png",     "Road Time"),
    ]

    saved_paths = []

    for col_name, filename, x_label in time_plots:
        # Verifica che la colonna esista
        if col_name in df.columns:
            # Imposta una figura più stretta
            plt.figure(figsize=(3,4))
            ax = df[[col_name]].boxplot(return_type='axes')
            # Imposta l'etichetta dell'asse x con il testo desiderato
            ax.set_xticklabels([x_label])
            # Imposta l'etichetta dell'asse y
            ax.set_ylabel("Minuti")
            plt.tight_layout()

            save_path = os.path.join(variant_dir, filename)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"{filename} salvato in {save_path}")
            
            if show_plot:
                plt.show()
            else:
                plt.close()

            saved_paths.append(save_path)
        else:
            print(f"ATTENZIONE: la colonna '{col_name}' non è presente nel DataFrame.")

    return saved_paths


def calculate_and_save_stats(variant_name, requests):
    """
    Legge il file CSV contenente gli assignments degli operatori e calcola le statistiche globali:
      - Assigned Requests: somma dei Num Requests
      - Total Waiting Time: somma dei Waiting Time
      - Total Road Time: somma dei Road Time
      - Average Waiting Time: media dei Waiting Time
      - Average Road Time: media dei Road Time
      - Total Cost: Routing Cost + Overtime Cost
      - Routing Cost: Total Road Time in minuti * 0.37
      - Overtime Cost: Total Overtime in minuti * 0.29
      - Total Overtime: somma degli Overtime
      - Total Hours Worked: somma dei Total Hours Worked
      - Occupation Ratio: (Total Hours Worked / Max Weekly Hours_totali) * 100
     
    I tempi sono espressi nel formato "HH:MM" (oppure "No overtime", interpretato come 0).
    Il file CSV viene letto da:
      RESULTS_DIR/variant_{variant_name}/global_assignments_{variant_name}.csv
    La statistica risultante viene salvata come file CSV
      RESULTS_DIR/variant_{variant_name}/stats_{variant_name}.csv
    """
    import os
    import pandas as pd

    csv_path = os.path.join(RESULTS_DIR,
                            f"variant_{variant_name}",
                            f"global_assignments_{variant_name}.csv")
    
    if not os.path.exists(csv_path):
        print(f"Il file {csv_path} non esiste.")
        return

    df = pd.read_csv(csv_path)

    # Calcolo delle statistiche
    total_assigned = df["Num Requests"].sum()

    waiting_minutes = df["Waiting Time"].apply(time_str_to_minutes)
    road_minutes    = df["Road Time"].apply(time_str_to_minutes)
    overtime_minutes= df["Overtime"].apply(time_str_to_minutes)
    worked_minutes  = df["Total Hours Worked"].apply(time_str_to_minutes)
    max_minutes     = df["Max Weekly Hours"].apply(time_str_to_minutes)
    
    total_waiting = waiting_minutes.sum()
    total_road    = road_minutes.sum()
    total_overtime= overtime_minutes.sum()
    total_worked  = worked_minutes.sum()
    total_max     = max_minutes.sum()

    n_ops = len(df)
    avg_waiting = total_waiting / n_ops if n_ops else 0
    avg_road    = total_road / n_ops if n_ops else 0

    # Calcolo dei costi
    routing_cost  = total_road * 0.37
    overtime_cost = total_overtime * 0.29
    total_cost    = routing_cost + overtime_cost

    # Calcolo del rapporto di occupazione

    requests_map = { str(r["id"]): r["duration"] for r in requests }
    total_service_time = sum(r["duration"] for r in requests)
    assigned_service_time = 0
    for idx, row in df.iterrows():
        assigned_ids = row["Assigned Requests"]
        if pd.isna(assigned_ids) or not assigned_ids.strip():
            continue
        for rid in assigned_ids.split(","):
            rid = rid.strip()
            if rid in requests_map:
                assigned_service_time += requests_map[rid]
    
    occupation_ratio = (assigned_service_time / total_service_time * 100) if total_service_time > 0 else 0

    # Funzione per convertire i minuti in formato "H:MM"
    def parse_minutes_to_hours(time_value):
        total = int(round(time_value))
        hours = total // 60
        minutes = total % 60
        return f"{hours}:{minutes:02d}"

    stats = {
        "Assigned Requests": total_assigned,
        "Total Waiting Time": parse_minutes_to_hours(total_waiting),
        "Total Road Time": parse_minutes_to_hours(total_road),
        "Average Waiting Time": parse_minutes_to_hours(avg_waiting),
        "Average Road Time": parse_minutes_to_hours(avg_road),
        "Total Cost": round(total_cost, 2),
        "Routing Cost": round(routing_cost, 2),
        "Overtime Cost": round(overtime_cost, 2),
        "Total Overtime": parse_minutes_to_hours(total_overtime),
        "Total Hours Worked": parse_minutes_to_hours(total_worked),
        "Occupation Ratio": round(occupation_ratio, 2)
    }

    # Salva le statistiche in un CSV
    stats_df = pd.DataFrame([stats])
    output_file = os.path.join(RESULTS_DIR,
                               f"variant_{variant_name}",
                               f"global_statistics_{variant_name}.csv")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    stats_df.to_csv(output_file, index=False)
    print(f"Statistiche salvate in {output_file}")


def save_operator_scheduling(operators, baseline_operators, tau, variant_name, day, session):
    """
    Salva le assegnazioni dei singoli operatori in file di testo separati per il giorno e la sessione indicati.
    
    Il file di ciascun operatore verrà salvato in:
      RESULT_DIR/variant_<variant_name>/scheduling/day_<day>/session_<session>/scheduling_S<session>_Op<operator_id>.txt
      
    Per ogni assegnazione "nuova" (quelle in op["Lo"] non presenti in baseline_operators["Lo"]),
    viene scritto:
    
        Operatore <id>: <Name> <Surname>
        
        Richiesta (id: <id>, Alpha: <Alpha>, Beta: <Beta>, b_i: <b_i>, t_i: <t_i>)
        ↓ Tau: <tau_value> - Waiting_time: <waiting_time>
        (per tutte tranne l’ultima assegnazione)
    
    Dove:
      - Ogni assegnazione è rappresentata da una tupla (req, b_i) in op["Lo"].
      - I campi Alpha, Beta e t_i devono essere presenti nel dizionario della richiesta.
      - Tau viene letto dal dizionario tau, utilizzando come chiave la coppia
          (operator["current_patient_id"], request["project_id"])
      - Waiting_time si calcola come: next_b_i - (b_i + t_i)
    """
    import os
    from utils import RESULTS_DIR

    base_sched_dir = os.path.join(RESULTS_DIR, f"variant_{variant_name}", "scheduling", f"day_{day}", f"session_{session}")
    os.makedirs(base_sched_dir, exist_ok=True)

    for op, base_op in zip(operators, baseline_operators):
        base_ids = {assignment[0]["id"] for assignment in base_op.get("Lo", [])}
        new_assignments = [assignment for assignment in op.get("Lo", []) if assignment[0]["id"] not in base_ids]

        # Costruisce il  file per l'operatore: es. scheduling_Sm_Op0.txt
        filename = f"scheduling_S{session}_Op{op['id']}.txt"
        file_path = os.path.join(base_sched_dir, filename)

        with open(file_path, "w") as f_out:
            header = f"Operatore ID: {op['id']}\n\n"
            f_out.write(header)

            if not new_assignments:
                f_out.write("Nessuna richiesta assegnata in questa sessione\n")
            else:

                current_location = op.get("current_patient_id", "")
                for i, (req, b_i) in enumerate(new_assignments):
                    req_id = req.get("id", "")
                    project_id = req.get("project_id", "")
                    alpha = req.get("min_time_begin", "")
                    beta  = req.get("max_time_begin", "")
                    t_i   = req.get("duration", "")
                    line_req = f"Richiesta (id: {req_id}, Alpha: {alpha}, Beta: {beta}, b_i: {b_i}, t_i: {t_i})\n"
                    f_out.write(line_req)

                    if i < len(new_assignments) - 1:
                        next_req, next_b_i = new_assignments[i+1]
                        try:
                            finish_time = int(b_i) + int(t_i)
                            waiting_time = int(next_b_i) - finish_time
                        except Exception:
                            waiting_time = ""
                        # Usa la coppia (current_location, req["project_id"]) per recuperare tau_value
                        tau_value = tau.get((current_location, req.get("project_id", "")), "")
                        line_info = f"↓ Tau: {tau_value} - Waiting_time: {waiting_time}\n"
                        f_out.write(line_info)
                        # Aggiorna la current_location al progetto della richiesta attuale
                        current_location = req.get("project_id", current_location)
                f_out.write("\n\n")
        print(f"Scheduling salvato in: {file_path}")