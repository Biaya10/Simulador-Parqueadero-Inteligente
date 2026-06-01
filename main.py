"""
main.py — Punto de entrada del Simulador de Parqueadero Inteligente

Flujo de arranque:
  1. Crear/verificar la BD y las tablas
  2. Inicializar el parqueadero (5 plazas por defecto)
  3. Crear las instancias de Parqueadero y Simulacion
  4. Lanzar la ventana Tkinter

"""

import tkinter as tk
import database as db
from parqueadero import Parqueadero
from simulacion import Simulacion
from gui import VentanaPrincipal
import queue


def main():
    # ── 1. Inicializar base de datos ──────────────────────────────────────
    db.crear_tablas()
    db.inicializar_parqueadero(n_plazas=5)

    # ── 2. Crear instancias del dominio ───────────────────────────────────
    parqueadero = Parqueadero(n_plazas=5)
    gui_queue = queue.Queue()
    simulacion = Simulacion(parqueadero, gui_queue)

    # ── 3. Lanzar GUI Tkinter ─────────────────────────────────────────────
    root = tk.Tk()
    root.geometry("980x680")

    app = VentanaPrincipal(root, parqueadero, simulacion)
    # La ventana usa su propio gui_queue interno; sincronizar referencia
    simulacion.gui_queue = app.gui_queue

    def al_cerrar():
        simulacion.detener()
        db.cerrar()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", al_cerrar)
    root.mainloop()


if __name__ == "__main__":
    main()
