"""
parqueadero.py — Lógica de negocio y control de concurrencia

Conceptos de SO aplicados:
  - Semaphore(N): controla acceso a N recursos (plazas).
    acquire() bloquea el hilo si no hay plazas disponibles.
    release() desbloquea el siguiente hilo en espera.
  - Lock: exclusión mutua para la sección crítica (búsqueda y
    asignación de plaza). Evita que dos hilos elijan la misma plaza.
  - threading.Event: señal de parada limpia para la simulación.

Analogía SO:
  Semaphore  → portero del parqueadero (cuenta cupos)
  Lock       → caseta de registro (un vehículo a la vez)
  Event      → botón de emergencia (detiene todo ordenadamente)
"""

import threading
import time
from datetime import datetime
import database as db


class Parqueadero:
    """
    Gestiona el acceso concurrente al parqueadero.

    El flujo de un vehículo es:
      1. semaforo.acquire()     ← espera si no hay cupo (BLOQUEO)
      2. with _lock:            ← sección crítica (EXCLUSIÓN MUTUA)
           buscar plaza libre
           actualizar BD
      3. ... esperar tiempo estacionado ...
      4. with _lock:            ← sección crítica al salir
           liberar plaza en BD
      5. semaforo.release()     ← libera cupo para el siguiente
    """

    def __init__(self, n_plazas: int = 5):
        self.n_plazas = n_plazas

        # Semáforo de conteo: valor inicial = número de plazas disponibles.
        # Dijkstra (1965): P() = acquire(), V() = release()
        self._semaforo = threading.Semaphore(n_plazas)

        # Mutex: protege la sección crítica (asignación de plaza en BD).
        # Sin este lock puede ocurrir race condition: dos hilos leen
        # "plaza 1 libre" simultáneamente y ambos la asignan.
        self._lock = threading.Lock()

        # Contadores en memoria (accedidos siempre dentro del lock)
        self._ocupados = 0

    # ── Propiedades de solo lectura ───────────────────────────────────────────

    @property
    def ocupados(self) -> int:
        with self._lock:
            return self._ocupados

    @property
    def libres(self) -> int:
        return self.n_plazas - self.ocupados

    # ── Operaciones principales ───────────────────────────────────────────────

    def ingresar(self, vehiculo_id: int, placa: str, gui_queue, stop_event: threading.Event) -> bool:
        """
        Intenta estacionar un vehículo.

        Bloquea en semaforo.acquire() hasta que haya una plaza libre.
        Retorna True si el vehículo fue estacionado, False si se canceló
        por el stop_event antes de conseguir plaza.
        """
        # Registrar que el vehículo está esperando
        db.registrar_evento("espera", vehiculo_id,
                            f"{placa} esperando plaza — {self.libres} libres")
        gui_queue.put({
            "tipo": "log",
            "mensaje": f"{placa} esperando...",
            "nivel": "espera"
        })

        # ── BLOQUEO: acquire() espera hasta que haya plaza ──────────────────
        # Si stop_event se activa mientras espera, usamos timeout corto
        # para poder verificar la señal de parada periódicamente.
        while not stop_event.is_set():
            adquirido = self._semaforo.acquire(timeout=0.5)
            if adquirido:
                break
        else:
            # Simulación detenida antes de conseguir plaza
            return False

        if stop_event.is_set():
            self._semaforo.release()
            return False

        # ── SECCIÓN CRÍTICA: Lock para asignar plaza ─────────────────────────
        # Solo un hilo a la vez puede buscar y asignar la plaza libre.
        with self._lock:
            plaza = db.obtener_plaza_libre()
            if plaza is None:
                # No debería ocurrir (el semáforo lo previene), pero por seguridad
                self._semaforo.release()
                return False

            hora_ingreso = datetime.now().strftime("%H:%M:%S")
            db.actualizar_ingreso(vehiculo_id, plaza["id"], hora_ingreso)
            self._ocupados += 1

            db.registrar_evento("ingreso", vehiculo_id,
                                f"{placa} → Plaza {plaza['numero']}")
            gui_queue.put({
                "tipo": "ingreso",
                "placa": placa,
                "plaza": plaza["numero"],
                "hora": hora_ingreso,
                "mensaje": f"{placa} estacionó en Plaza {plaza['numero']}",
                "nivel": "ingreso"
            })

        return True

    def salir(self, vehiculo_id: int, placa: str, plaza_id: int,
              plaza_numero: int, tiempo_estacionado: float, gui_queue):
        """
        Registra la salida del vehículo y libera la plaza.
        """
        hora_salida = datetime.now().strftime("%H:%M:%S")

        # ── SECCIÓN CRÍTICA: actualizar BD y contadores ──────────────────────
        with self._lock:
            db.actualizar_salida(vehiculo_id, plaza_id, hora_salida, tiempo_estacionado)
            self._ocupados = max(0, self._ocupados - 1)

            db.registrar_evento("salida", vehiculo_id,
                                f"{placa} salió de Plaza {plaza_numero} "
                                f"({tiempo_estacionado:.1f}s)")
            gui_queue.put({
                "tipo": "salida",
                "placa": placa,
                "plaza": plaza_numero,
                "hora": hora_salida,
                "tiempo": tiempo_estacionado,
                "mensaje": f"{placa} salió de Plaza {plaza_numero} ({tiempo_estacionado:.1f}s)",
                "nivel": "salida"
            })

        # ── LIBERAR CUPO: desbloquea el siguiente hilo en espera ─────────────
        # V() en la notación de Dijkstra
        self._semaforo.release()

    def reiniciar(self, n_plazas: int):
        """Reinicia el semáforo y contadores para una nueva simulación."""
        self.n_plazas = n_plazas
        self._semaforo = threading.Semaphore(n_plazas)
        with self._lock:
            self._ocupados = 0

    def estado(self) -> dict:
        """Snapshot del estado actual (para la GUI)."""
        with self._lock:
            return {
                "total": self.n_plazas,
                "ocupados": self._ocupados,
                "libres": self.n_plazas - self._ocupados,
            }
