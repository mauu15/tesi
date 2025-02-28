# Funzioni e classi per la gestione degli operatori e delle richieste

from typing import Optional, Tuple

class Node:
    def __init__(self, id: int, coordinates: Tuple[float, float]):
        """
        Classe Node

        :param id: Identificativo univoco del nodo.
        :param coordinates: Coppia di coordinate (latitudine, longitudine) oppure qualsiasi altra rappresentazione spaziale.
        """
        self.id = id
        self.coordinates = coordinates

    def __repr__(self) -> str:
        return f"Node(id={self.id}, coordinates={self.coordinates})"


class Operator:
    def __init__(self, id: int, home: Node, work_time: int = 300, current_patient: Optional[Node] = None, t0: int = 420, cluster_id: Optional[int] = None):
        """
        Classe Operatore

        :param id: Id dell'operatore.
        :param home: Nodo di partenza (depot) dell'operatore, di tipo Node.
        :param work_time: Tempo di lavoro disponibile per l'operatore per effettuare visite.
        :param current_patient: Il paziente attuale assegnato all'operatore, rappresentato come Node.
        :param t0: Il primo momento disponibile per l'operatore per servire una richiesta, 420 = morning shift, 960 = afternoon shift.
        :param cluster_id: Identificativo del cluster a cui appartiene l'operatore.
        """
        self.id = id
        self.home = home
        self.work_time = work_time
        
        # Se non viene specificato un current_patient, l'operatore inizia dal suo depot (home)
        self.current_patient = current_patient if current_patient is not None else home
        self.t0 = t0
        self.cluster_id = cluster_id

    def __repr__(self) -> str:
        return (f"Operator(id={self.id}, home={self.home}, work_time={self.work_time:.0f}, "
                f"current_patient={self.current_patient}, t0={self.t0}, cluster_id={self.cluster_id})")


class Request:
    def __init__(self, i: int, patient: Node, duration: int, temporal_window: Tuple[int, int], cluster_id: int):
        """
        Classe Richiesta

        :param i: Identificativo della richiesta.
        :param patient: Nodo di partenza della richiesta, di tipo Node.
        :param duration: Durata della richiesta in minuti.
        :param patient: Paziente associato alla richiesta.
        :param temporal_window: Finestra temporale in cui la richiesta deve essere servita (α, β).
        :param cluster_id: Identificativo del cluster a cui appartiene la richiesta.
        """
        self.i = i
        self.patient = patient
        self.duration = duration
        self.temporal_window = temporal_window
        self.cluster_id = cluster_id

    def __repr__(self) -> str:
        return (f"Request(i={self.i}, patient={self.patient}, duration={self.duration}, "
                f"patient='{self.patient}', temporal_window={self.temporal_window}, cluster_id={self.cluster_id})")
