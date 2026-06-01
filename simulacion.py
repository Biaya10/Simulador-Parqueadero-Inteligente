"""
simulacion.py — Motor de simulación (hilos de vehículos)

Cada VehiculoThread representa un proceso/hilo del SO que compite
por el recurso limitado (plazas del parqueadero).

Conceptos de SO aplicados:
  - threading.Thread: proceso ligero independiente
  - threading.Event:  señal de parada (como una interrupción del SO)
  - daemon=True:      el hilo muere si el proceso principal termina
  - random.seed():    reproducibilidad de la simulación
"""

import threading
import time
import random
import string
import database as db


# ── Hilo de vehículo ──────────────────────────────────────────────────────────

class VehiculoThread(threading.Thread):
    """
    Simula el ciclo de vida completo de un vehículo:
      1. Llegar al parqueadero (ingresar)
      2. Esperar si no hay plaza (bloqueado en semáforo)
      3. Estacionarse (sección crítica)
      4. Esperar tiempo aleatorio (simulando permanencia)
      5. Salir (liberar plaza y semáforo)
    """

    def __init__(self, placa: str, parqueadero, gui_queue,
                 stop_event: threading.Event,
                 tiempo_min: float = 2.0, tiempo_max: float = 8.0):
        super().__init__(name=f"Veh-{placa}", daemon=True)
        self.placa = placa
        self.parqueadero = parqueadero
        self.gui_queue = gui_queue
        self.stop_event = stop_event
        self.tiempo_min = tiempo_min
        self.tiempo_max = tiempo_max

    def run(self):
        """
        Punto de entrada del hilo. Se ejecuta en paralelo con otros hilos.
        El SO decide cuándo le toca CPU a este hilo.
        """
        # Insertar vehículo en la BD (estado inicial: 'esperando')
        vehiculo_id = db.insertar_vehiculo(self.placa)
        if vehiculo_id is None:
            # Placa duplicada — obtener el id existente
            v = db.buscar_vehiculo(self.placa)
            if v:
                vehiculo_id = v["id"]
            else:
                return

        # Notificar a la GUI que llegó un nuevo vehículo
        self.gui_queue.put({
            "tipo": "nuevo_vehiculo",
            "placa": self.placa,
            "mensaje": f"{self.placa} llegó al parqueadero",
            "nivel": "info"
        })

        # ── Intentar ingresar (puede bloquearse aquí) ─────────────────────
        estacionado = self.parqueadero.ingresar(
            vehiculo_id, self.placa, self.gui_queue, self.stop_event
        )

        if not estacionado or self.stop_event.is_set():
            return

        # ── Obtener info de la plaza asignada ─────────────────────────────
        vehiculo = db.buscar_vehiculo(self.placa)
        if not vehiculo or vehiculo["plaza_id"] is None:
            return

        plaza_id = vehiculo["plaza_id"]

        # Consultar número de plaza para el log
        plazas = db.obtener_plazas()
        plaza_numero = next(
            (p["numero"] for p in plazas if p["id"] == plaza_id), plaza_id
        )

        # ── Permanecer estacionado un tiempo aleatorio ────────────────────
        tiempo_estacionado = random.uniform(self.tiempo_min, self.tiempo_max)

        # Esperar en pequeños intervalos para poder responder al stop_event
        inicio = time.time()
        while time.time() - inicio < tiempo_estacionado:
            if self.stop_event.is_set():
                break
            time.sleep(0.2)

        if self.stop_event.is_set():
            return

        # ── Salir del parqueadero ─────────────────────────────────────────
        tiempo_real = round(time.time() - inicio, 2)
        self.parqueadero.salir(
            vehiculo_id, self.placa, plaza_id, plaza_numero,
            tiempo_real, self.gui_queue
        )


# ── Controlador de la simulación ──────────────────────────────────────────────

class Simulacion:
    """
    Crea y gestiona los hilos de vehículos.

    Expone tres operaciones:
      iniciar()   — lanza N hilos con llegadas escalonadas
      detener()   — activa el Event de parada (todos los hilos terminan limpiamente)
      reiniciar() — detiene la simulación actual y la relanza
    """

    def __init__(self, parqueadero, gui_queue):
        self.parqueadero = parqueadero
        self.gui_queue = gui_queue
        self._stop_event = threading.Event()
        self._stop_event.set()  # Estado inicial: "detenido, listo para iniciar"
        self._hilos: list[VehiculoThread] = []
        self._hilo_lanzador: threading.Thread | None = None

    @property
    def activa(self) -> bool:
        return not self._stop_event.is_set()

    def iniciar(self, n_vehiculos: int, tiempo_min: float, tiempo_max: float,
                intervalo_llegada: float, seed: int | None = 42):
        """
        Lanza n_vehiculos hilos. Los vehículos llegan con un intervalo
        aleatorio entre llegadas para simular tráfico real.

        seed=42 garantiza reproducibilidad en demos.
        """
        if not self._stop_event.is_set():
            return  # ya hay una simulación activa

        random.seed(seed)
        self._stop_event.clear()
        self._hilos.clear()

        # Lanzar un hilo coordinador que crea los vehículos gradualmente
        self._hilo_lanzador = threading.Thread(
            target=self._lanzar_vehiculos,
            args=(n_vehiculos, tiempo_min, tiempo_max, intervalo_llegada),
            daemon=True,
            name="Lanzador"
        )
        self._hilo_lanzador.start()

    def _lanzar_vehiculos(self, n_vehiculos, tiempo_min, tiempo_max, intervalo_llegada):
        """Hilo interno que crea vehículos con llegadas escalonadas."""
        for i in range(n_vehiculos):
            if self._stop_event.is_set():
                break

            placa = _generar_placa(i)
            hilo = VehiculoThread(
                placa, self.parqueadero, self.gui_queue,
                self._stop_event, tiempo_min, tiempo_max
            )
            self._hilos.append(hilo)
            hilo.start()

            self.gui_queue.put({
                "tipo": "actualizar_estado",
                "mensaje": None,
                "nivel": "info"
            })

            # Esperar antes de lanzar el siguiente vehículo
            espera = random.uniform(0.3, intervalo_llegada)
            time.sleep(espera)

        # Cuando todos los hilos terminen, notificar a la GUI
        for h in self._hilos:
            h.join(timeout=60)

        if not self._stop_event.is_set():
            self.gui_queue.put({
                "tipo": "simulacion_terminada",
                "mensaje": "Simulación completada",
                "nivel": "info"
            })

    def detener(self):
        """Activa la señal de parada. Los hilos terminan en su próxima verificación."""
        self._stop_event.set()

    def reiniciar(self, n_plazas: int, n_vehiculos: int,
                  tiempo_min: float, tiempo_max: float,
                  intervalo_llegada: float, seed: int | None = 42):
        """Detiene la simulación actual y relanza con nuevos parámetros."""
        self.detener()
        # Esperar a que los hilos terminen (máx 3s)
        if self._hilo_lanzador:
            self._hilo_lanzador.join(timeout=3)

        # Reiniciar parqueadero y BD
        db.inicializar_parqueadero(n_plazas)
        self.parqueadero.reiniciar(n_plazas)

        self.iniciar(n_vehiculos, tiempo_min, tiempo_max, intervalo_llegada, seed)

    def hilos_activos(self) -> int:
        """Cuenta los hilos de vehículos que siguen vivos."""
        return sum(1 for h in self._hilos if h.is_alive())


# ── Utilidades ────────────────────────────────────────────────────────────────

def _generar_placa(indice: int) -> str:
    """
    Genera una placa con formato colombiano: ABC-123.
    Usa letras/números predeterminados para reproducibilidad.
    """
    letras = "".join(random.choices(string.ascii_uppercase, k=3))
    numeros = "".join(random.choices(string.digits, k=3))
    return f"{letras}-{numeros}"
