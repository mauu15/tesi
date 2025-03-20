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
    s = str(time_value)
    if '.' in s:
        parts = s.split('.')
        hour = int(parts[0])
        minute = int(parts[1])
        return hour * 60 + minute
    else:
        return int(float(s) * 60)

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
        data.append({
            "Operator ID": op["id"],
            "Name": op["name"],
            "Surname": op["surname"],
            "Assigned Requests": ", ".join(str(x[1]) for x in op["Lo"]),
            "Num Requests": len(op["Lo"]),
            "Total Hours Worked": parse_minutes_to_hours(op["wo"]),
            "Max Weekly Hours": parse_minutes_to_hours(op["Ho"]),
            "Road Time": parse_minutes_to_hours(op["road_time"]),
            "Waiting Time": parse_minutes_to_hours(op["do"])
        })
    return pd.DataFrame(data)

    
def display_global_statistics(operators):
    """
    Calcola alcune statistiche globali dai dati dei singoli operatori:
      - Total Requests: somma delle richieste mattutine e pomeridiane eseguite
      - Total Waiting Time: somma totale del waiting time (in formato H.MM)
      - Total Road Time: somma dei tempi di spostamento
      - Average Waiting Time: media dei waiting time degli operatori
      - Average Road Time: media dei road time degli operatori
    """
    import pandas as pd
    total_requests = sum(len(op["morning_requests"]) + len(op["afternoon_requests"]) for op in operators)
    total_waiting = sum(op["d_o"] for op in operators)
    total_road = sum(op["road_time"] for op in operators)
    avg_waiting = total_waiting / len(operators) if operators else 0
    avg_road = total_road / len(operators) if operators else 0

    stats = {
        "Total Requests": total_requests,
        "Total Waiting Time": parse_minutes_to_hours(total_waiting),
        "Total Road Time": parse_minutes_to_hours(total_road),
        "Average Waiting Time": parse_minutes_to_hours(avg_waiting),
        "Average Road Time": parse_minutes_to_hours(avg_road)
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
    import os, json
    folder_path = f"tesi/results/variant_{variant_name}/day_{day}/session_{session}/k_{k}"
    os.makedirs(folder_path, exist_ok=True)
    
    cost_ds_str = {f"{key[0]}_{key[1]}": value for key, value in cost_ds.items()}

    
    
    data = {
        "variant": variant_name,
        "day": day,
        "session": session,
        "k": k,
        "cost_ds": cost_ds_str,
        "total_cost": total_cost
    }

    out_file = os.path.join(folder_path, "stats.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    
    # Salvataggio global statistics in CSV
    global_csv = os.path.join(folder_path, "global_statistics.csv")
    global_stats_df.to_csv(global_csv, index=False)
    
    # Salvataggio assignments (con turni) in CSV
    assignments_csv = os.path.join(folder_path, "assignments.csv")
    assignments_df.to_csv(assignments_csv, index=False)