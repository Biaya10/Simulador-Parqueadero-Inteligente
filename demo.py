"""
demo.py — Script de Demostración Reproducible

Ejecutar sin interfaz gráfica para ver el comportamiento del sistema
en consola. Demuestra:
  - Concurrencia real con múltiples threads
  - Bloqueo en semáforo cuando no hay plazas
  - Sincronización sin race conditions
  - Reproducibilidad con seed=42

Uso:
    python demo.py

Output:
    Muestra en tiempo real cada evento (ingreso, salida, espera)
    con timestamps exactos.
"""

import time
import random
import database as db
from parqueadero import Parqueadero
from simulacion import Simulacion
import queue
import threading


def demo_completa():
    """Demostración 1: Simulación completa con 10 vehículos y 3 plazas."""
    print("\n" + "="*70)
    print("DEMO 1: Parqueadero con 3 plazas, 10 vehículos")
    print("="*70)
    print("\nConceptos SO demostrados:")
    print("  [*] Semaphore: bloquea vehículos cuando no hay cupos")
    print("  [*] Lock: exclusion mutua al asignar plazas")
    print("  [*] Threading: cada vehículo es un hilo independiente")
    print("  [*] Queue: comunicación segura hilo -> aplicación principal")
    print("\nIniciando simulación...")
    print("-" * 70)

    # Configuración
    n_plazas = 3
    n_vehiculos = 10
    db.crear_tablas()
    db.inicializar_parqueadero(n_plazas)

    parqueadero = Parqueadero(n_plazas)
    gui_queue = queue.Queue()
    simulacion = Simulacion(parqueadero, gui_queue)

    # Iniciar simulación
    simulacion.iniciar(
        n_vehiculos=n_vehiculos,
        tiempo_min=1.0,
        tiempo_max=3.0,
        intervalo_llegada=0.5,
        seed=42  # reproducibilidad
    )

    # Monitorear en tiempo real
    ultima_actualizacion = time.time()
    while simulacion.hilos_activos() > 0 or not gui_queue.empty():
        # Procesar cola de eventos
        try:
            while True:
                msg = gui_queue.get_nowait()
                _imprimir_evento(msg)
        except queue.Empty:
            pass

        # Mostrar estado cada 2 segundos
        ahora = time.time()
        if ahora - ultima_actualizacion > 2:
            estado = parqueadero.estado()
            print(f"\n[{time.strftime('%H:%M:%S')}] Estado: "
                  f"{estado['ocupados']}/{estado['total']} ocupadas, "
                  f"{simulacion.hilos_activos()} hilos activos")
            ultima_actualizacion = ahora

        time.sleep(0.1)

    # Esperar a que terminen los últimos eventos
    time.sleep(1)

    print("\n" + "-" * 70)
    print("Simulación completada.")
    _mostrar_resumen()


def demo_bloqueo():
    """Demostración 2: Bloqueo de vehículos en semáforo lleno."""
    print("\n" + "="*70)
    print("DEMO 2: Bloqueo en Semaphore (1 plaza, 5 vehículos)")
    print("="*70)
    print("\nDemostración clara de bloqueo en semáforo:")
    print("  • Semaphore empieza en 1 (1 plaza disponible)")
    print("  • Primer vehículo entra → Semaphore = 0")
    print("  • Siguientes vehículos se bloquean en acquire()")
    print("  • Primer vehículo sale → Semaphore = 1, desbloquea un vehículo")
    print("\nIniciando simulación...")
    print("-" * 70)

    n_plazas = 1
    n_vehiculos = 5
    db.crear_tablas()
    db.inicializar_parqueadero(n_plazas)

    parqueadero = Parqueadero(n_plazas)
    gui_queue = queue.Queue()
    simulacion = Simulacion(parqueadero, gui_queue)

    simulacion.iniciar(
        n_vehiculos=n_vehiculos,
        tiempo_min=2.0,
        tiempo_max=2.5,
        intervalo_llegada=0.3,
        seed=42
    )

    while simulacion.hilos_activos() > 0 or not gui_queue.empty():
        try:
            while True:
                msg = gui_queue.get_nowait()
                _imprimir_evento(msg)
        except queue.Empty:
            pass
        time.sleep(0.1)

    time.sleep(1)
    print("\n" + "-" * 70)
    print("Nota: Con 1 plaza, solo 1 vehículo puede estar adentro.")
    print("Los demás esperan bloqueados en Semaphore.acquire().")
    _mostrar_resumen()


def demo_stats():
    """Demostración 3: Estadísticas y exportación CSV."""
    print("\n" + "="*70)
    print("DEMO 3: Estadísticas y exportación")
    print("="*70)

    n_plazas = 4
    n_vehiculos = 8
    db.crear_tablas()
    db.inicializar_parqueadero(n_plazas)

    parqueadero = Parqueadero(n_plazas)
    gui_queue = queue.Queue()
    simulacion = Simulacion(parqueadero, gui_queue)

    print(f"\nSimulación: {n_plazas} plazas, {n_vehiculos} vehículos")
    print("Iniciando...")

    simulacion.iniciar(n_vehiculos, 1.5, 3.0, 0.5, seed=42)

    while simulacion.hilos_activos() > 0:
        try:
            while True:
                gui_queue.get_nowait()
        except queue.Empty:
            pass
        time.sleep(0.1)

    time.sleep(1)

    print("\n" + "-" * 70)
    print("Estadísticas finales:")
    _mostrar_resumen()

    # Exportar CSV
    import os
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "logs", "demo_eventos.csv"
    )
    from metricas import exportar_csv
    ok, msg = exportar_csv(csv_path)
    if ok:
        print(f"\n[OK] CSV exportado: {csv_path}")
        # Mostrar primeras líneas
        with open(csv_path) as f:
            lineas = f.readlines()[:6]
            print("\nPrimeras lineas del CSV:")
            for linea in lineas:
                print("  " + linea.rstrip())
    else:
        print(f"\n[ERROR] {msg}")


def _imprimir_evento(msg: dict):
    """Imprime un evento de forma legible."""
    tipo = msg.get("tipo", "")
    mensaje = msg.get("mensaje", "")

    if not mensaje:
        return

    ts = time.strftime("%H:%M:%S")
    nivel = msg.get("nivel", "info")

    # Colores ANSI simples (Windows 10+ soporta)
    colores = {
        "ingreso": "\033[92m",  # verde
        "salida": "\033[91m",   # rojo
        "espera": "\033[93m",   # amarillo
        "info": "\033[94m",     # azul
    }
    reset = "\033[0m"

    color = colores.get(nivel, reset)
    print(f"{color}[{ts}] {mensaje}{reset}")


def _mostrar_resumen():
    """Muestra el resumen de métricas finales."""
    from metricas import resumen

    stats = resumen()
    print("\nResumen de simulación:")
    print(f"  Total de plazas:        {stats['total_plazas']}")
    print(f"  Libres:                 {stats['libres']}")
    print(f"  Ocupadas:               {stats['ocupadas']}")
    print(f"  Uso del parqueadero:    {stats['uso_pct']:.1f}%")
    print(f"  Vehículos atendidos:    {stats['atendidos']}")
    print(f"  Tiempo promedio:        {stats['t_promedio_s']:.2f}s")

    eventos = db.obtener_eventos(10)
    print(f"\n  Total de eventos:       {len(db.obtener_eventos(10000))}")
    print("\n  Últimos 5 eventos:")
    for e in eventos[:5]:
        ts = e.get("timestamp", "")
        tipo = e.get("tipo", "")
        placa = e.get("placa", "?")
        detalle = e.get("detalle", "")
        print(f"    [{ts}] {tipo:8} {placa:8} {detalle[:40]}")


if __name__ == "__main__":
    try:
        print("\n\n")
        print("=" * 70)
        print("SIMULADOR DE PARQUEADERO INTELIGENTE".center(70))
        print("Demostraciones de Concurrencia y SO".center(70))
        print("=" * 70)

        demo_completa()
        # demo_bloqueo()
        # demo_stats()

        print("\n[COMPLETADO] Demostraciones finalizadas.\n")

        db.cerrar()

    except KeyboardInterrupt:
        print("\n\n[INTERRUPCION] Simulacion interrumpida por el usuario.")
        db.cerrar()
    except Exception as e:
        print(f"\n\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.cerrar()
