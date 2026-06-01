"""
gui.py — Interfaz gráfica Tkinter

Regla de oro para Tkinter + threads:
  NUNCA modificar un widget desde un hilo secundario.
  Los hilos ponen mensajes en gui_queue; el hilo principal
  los consume cada 100ms via root.after().

Layout:
  ┌─────────────────────────────────────────────┐
  │  Título                                     │
  ├──────────────┬──────────────────────────────┤
  │ Panel estado │  Mapa de plazas (Canvas)      │
  ├──────────────┴──────────────────────────────┤
  │ Tabla vehículos  │  Log de eventos           │
  ├──────────────────┴──────────────────────────┤
  │ Panel métricas                              │
  ├─────────────────────────────────────────────┤
  │ Controles: [Iniciar][+Veh][Detener][Reset]  │
  └─────────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import queue
import database as db
import metricas as met

# ── Paleta de colores ─────────────────────────────────────────────────────────
COLOR_BG        = "#1e1e2e"
COLOR_PANEL     = "#2a2a3e"
COLOR_BORDE     = "#3a3a5c"
COLOR_TITULO    = "#cdd6f4"
COLOR_TEXTO     = "#cdd6f4"
COLOR_SUBTEXTO  = "#a6adc8"

COLOR_LIBRE     = "#a6e3a1"   # verde
COLOR_OCUPADA   = "#f38ba8"   # rojo
COLOR_ESPERA    = "#f9e2af"   # amarillo
COLOR_TEXTO_PZ  = "#1e1e2e"

COLOR_BTN_VERDE = "#a6e3a1"
COLOR_BTN_ROJO  = "#f38ba8"
COLOR_BTN_AZUL  = "#89b4fa"
COLOR_BTN_GRIS  = "#585b70"

LOG_COLORES = {
    "ingreso": "#a6e3a1",
    "salida":  "#f38ba8",
    "espera":  "#f9e2af",
    "info":    "#89dceb",
}


class VentanaPrincipal:
    """Ventana principal de la aplicación."""

    def __init__(self, root: tk.Tk, parqueadero, simulacion):
        self.root = root
        self.parqueadero = parqueadero
        self.simulacion = simulacion
        self.gui_queue: queue.Queue = queue.Queue()

        # Pasar la cola a la simulación
        self.simulacion.gui_queue = self.gui_queue

        self._plaza_rects: dict = {}   # id_plaza → id_rect en Canvas
        self._plaza_labels: dict = {}  # id_plaza → id_texto en Canvas
        self._n_plazas = 5

        self._construir_ventana()
        self._inicializar_vistas()
        self._procesar_cola()           # arranca el loop de la cola

    # ── Construcción de la ventana ────────────────────────────────────────────

    def _construir_ventana(self):
        self.root.title("Simulador de Parqueadero Inteligente")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(True, True)
        self.root.minsize(900, 650)

        self._frame_titulo()
        self._frame_superior()
        self._frame_medio()
        self._frame_metricas()
        self._frame_controles()

    def _frame_titulo(self):
        f = tk.Frame(self.root, bg=COLOR_PANEL, pady=8)
        f.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(f, text="SIMULADOR DE PARQUEADERO INTELIGENTE",
                 font=("Consolas", 14, "bold"),
                 bg=COLOR_PANEL, fg=COLOR_TITULO).pack()
        tk.Label(f, text="Python  ·  SQLite  ·  threading  ·  Tkinter",
                 font=("Consolas", 9), bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack()

    def _frame_superior(self):
        """Panel de estado + mapa de plazas."""
        f = tk.Frame(self.root, bg=COLOR_BG)
        f.pack(fill="x", padx=8, pady=4)

        # ── Panel estado (izquierda) ──────────────────────────────────────
        estado = tk.LabelFrame(f, text=" Estado ", bg=COLOR_PANEL,
                               fg=COLOR_SUBTEXTO, font=("Consolas", 9),
                               bd=1, relief="flat")
        estado.pack(side="left", fill="y", padx=(0, 4))

        self.lbl_total    = self._lbl_estado(estado, "Total plazas:", "5")
        self.lbl_libres   = self._lbl_estado(estado, "Libres:",       "5", COLOR_LIBRE)
        self.lbl_ocupados = self._lbl_estado(estado, "Ocupados:",     "0", COLOR_OCUPADA)
        self.lbl_espera   = self._lbl_estado(estado, "En espera:",    "0", COLOR_ESPERA)
        self.lbl_threads  = self._lbl_estado(estado, "Hilos activos:","0", COLOR_BTN_AZUL)

        # ── Mapa de plazas (derecha) ──────────────────────────────────────
        mapa_frame = tk.LabelFrame(f, text=" Mapa de Plazas ", bg=COLOR_PANEL,
                                   fg=COLOR_SUBTEXTO, font=("Consolas", 9),
                                   bd=1, relief="flat")
        mapa_frame.pack(side="left", fill="both", expand=True)

        self.canvas_mapa = tk.Canvas(mapa_frame, bg=COLOR_PANEL,
                                     height=110, highlightthickness=0)
        self.canvas_mapa.pack(fill="both", expand=True, padx=6, pady=6)

    def _lbl_estado(self, parent, texto, valor, color_valor=None):
        color_valor = color_valor or COLOR_TEXTO
        row = tk.Frame(parent, bg=COLOR_PANEL)
        row.pack(fill="x", padx=10, pady=2)
        tk.Label(row, text=texto, font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO, width=14, anchor="w").pack(side="left")
        lbl = tk.Label(row, text=valor, font=("Consolas", 10, "bold"),
                       bg=COLOR_PANEL, fg=color_valor, width=5, anchor="e")
        lbl.pack(side="left")
        return lbl

    def _frame_medio(self):
        """Tabla de vehículos + log de eventos."""
        f = tk.Frame(self.root, bg=COLOR_BG)
        f.pack(fill="both", expand=True, padx=8, pady=4)

        # ── Tabla vehículos ───────────────────────────────────────────────
        tabla_frame = tk.LabelFrame(f, text=" Vehículos ", bg=COLOR_PANEL,
                                    fg=COLOR_SUBTEXTO, font=("Consolas", 9),
                                    bd=1, relief="flat")
        tabla_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols = ("Placa", "Estado", "Plaza", "Ingreso", "Tiempo(s)")
        self.tabla = ttk.Treeview(tabla_frame, columns=cols,
                                  show="headings", height=10)
        anchos = {"Placa": 80, "Estado": 90, "Plaza": 50,
                  "Ingreso": 75, "Tiempo(s)": 70}
        for c in cols:
            self.tabla.heading(c, text=c)
            self.tabla.column(c, width=anchos[c], anchor="center")

        # Colores por estado
        self.tabla.tag_configure("estacionado", foreground=COLOR_LIBRE)
        self.tabla.tag_configure("esperando",   foreground=COLOR_ESPERA)
        self.tabla.tag_configure("salido",       foreground=COLOR_SUBTEXTO)

        scroll_t = ttk.Scrollbar(tabla_frame, orient="vertical",
                                 command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll_t.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        scroll_t.pack(side="right", fill="y")

        # Estilo del Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=COLOR_PANEL,
                        fieldbackground=COLOR_PANEL,
                        foreground=COLOR_TEXTO,
                        rowheight=22,
                        font=("Consolas", 9))
        style.configure("Treeview.Heading",
                        background=COLOR_BORDE,
                        foreground=COLOR_TITULO,
                        font=("Consolas", 9, "bold"))
        style.map("Treeview", background=[("selected", COLOR_BORDE)])

        # ── Log de eventos ────────────────────────────────────────────────
        log_frame = tk.LabelFrame(f, text=" Log de Eventos ", bg=COLOR_PANEL,
                                  fg=COLOR_SUBTEXTO, font=("Consolas", 9),
                                  bd=1, relief="flat")
        log_frame.pack(side="left", fill="both", expand=True)

        self.txt_log = tk.Text(log_frame, bg=COLOR_BG, fg=COLOR_TEXTO,
                               font=("Consolas", 9), state="disabled",
                               wrap="word", height=12)
        scroll_l = ttk.Scrollbar(log_frame, orient="vertical",
                                 command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll_l.set)

        for nivel, color in LOG_COLORES.items():
            self.txt_log.tag_configure(nivel, foreground=color)

        self.txt_log.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scroll_l.pack(side="right", fill="y")

    def _frame_metricas(self):
        """Panel de métricas en la parte inferior."""
        f = tk.LabelFrame(self.root, text=" Métricas ", bg=COLOR_PANEL,
                          fg=COLOR_SUBTEXTO, font=("Consolas", 9),
                          bd=1, relief="flat")
        f.pack(fill="x", padx=8, pady=2)

        inner = tk.Frame(f, bg=COLOR_PANEL)
        inner.pack(fill="x", padx=10, pady=4)

        self.lbl_atendidos  = self._met_lbl(inner, "Atendidos:", "0")
        self.lbl_t_promedio = self._met_lbl(inner, "T.Prom(s):", "0.0")
        self.lbl_uso        = self._met_lbl(inner, "Uso %:", "0.0")

    def _met_lbl(self, parent, texto, valor):
        f = tk.Frame(parent, bg=COLOR_PANEL)
        f.pack(side="left", padx=20)
        tk.Label(f, text=texto, font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack(side="left")
        lbl = tk.Label(f, text=valor, font=("Consolas", 10, "bold"),
                       bg=COLOR_PANEL, fg=COLOR_BTN_AZUL)
        lbl.pack(side="left", padx=4)
        return lbl

    def _frame_controles(self):
        """Barra de botones + configuración."""
        f = tk.Frame(self.root, bg=COLOR_PANEL, pady=6)
        f.pack(fill="x", padx=8, pady=(0, 8))

        # Configuración
        cfg = tk.Frame(f, bg=COLOR_PANEL)
        cfg.pack(side="left", padx=10)

        tk.Label(cfg, text="Plazas:", font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack(side="left")
        self.spin_plazas = tk.Spinbox(cfg, from_=1, to=20, width=3,
                                      font=("Consolas", 9),
                                      bg=COLOR_BG, fg=COLOR_TEXTO,
                                      buttonbackground=COLOR_BORDE)
        self.spin_plazas.delete(0, "end")
        self.spin_plazas.insert(0, "5")
        self.spin_plazas.pack(side="left", padx=(2, 10))

        tk.Label(cfg, text="Vehículos:", font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack(side="left")
        self.spin_vehiculos = tk.Spinbox(cfg, from_=1, to=50, width=3,
                                         font=("Consolas", 9),
                                         bg=COLOR_BG, fg=COLOR_TEXTO,
                                         buttonbackground=COLOR_BORDE)
        self.spin_vehiculos.delete(0, "end")
        self.spin_vehiculos.insert(0, "10")
        self.spin_vehiculos.pack(side="left", padx=(2, 10))

        tk.Label(cfg, text="T.min:", font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack(side="left")
        self.spin_tmin = tk.Spinbox(cfg, from_=1, to=30, width=3,
                                    font=("Consolas", 9),
                                    bg=COLOR_BG, fg=COLOR_TEXTO,
                                    buttonbackground=COLOR_BORDE)
        self.spin_tmin.delete(0, "end")
        self.spin_tmin.insert(0, "3")
        self.spin_tmin.pack(side="left", padx=(2, 4))

        tk.Label(cfg, text="T.max:", font=("Consolas", 9),
                 bg=COLOR_PANEL, fg=COLOR_SUBTEXTO).pack(side="left")
        self.spin_tmax = tk.Spinbox(cfg, from_=1, to=60, width=3,
                                    font=("Consolas", 9),
                                    bg=COLOR_BG, fg=COLOR_TEXTO,
                                    buttonbackground=COLOR_BORDE)
        self.spin_tmax.delete(0, "end")
        self.spin_tmax.insert(0, "8")
        self.spin_tmax.pack(side="left", padx=(2, 0))

        # Botones
        botones = tk.Frame(f, bg=COLOR_PANEL)
        botones.pack(side="right", padx=10)

        self._btn(botones, "▶ Iniciar",    COLOR_BTN_VERDE, self._cb_iniciar)
        self._btn(botones, "+ Vehículo",   COLOR_BTN_AZUL,  self._cb_agregar)
        self._btn(botones, "⏹ Detener",    COLOR_BTN_ROJO,  self._cb_detener)
        self._btn(botones, "↺ Reiniciar",  COLOR_BTN_GRIS,  self._cb_reiniciar)
        self._btn(botones, "⬇ Exportar",   COLOR_BTN_GRIS,  self._cb_exportar)

    def _btn(self, parent, texto, color, cmd):
        b = tk.Button(parent, text=texto, font=("Consolas", 9, "bold"),
                      bg=color, fg=COLOR_BG, activebackground=color,
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      command=cmd)
        b.pack(side="left", padx=3)
        return b

    # ── Inicialización de vistas ──────────────────────────────────────────────

    def _inicializar_vistas(self):
        n = int(self.spin_plazas.get())
        self._n_plazas = n
        self._dibujar_mapa(n)
        self._actualizar_contadores()
        self._actualizar_tabla()
        self._actualizar_metricas()

    # ── Mapa de plazas ────────────────────────────────────────────────────────

    def _dibujar_mapa(self, n_plazas: int):
        """Dibuja los rectángulos de las plazas en el Canvas."""
        self.canvas_mapa.delete("all")
        self._plaza_rects.clear()
        self._plaza_labels.clear()

        if n_plazas == 0:
            return

        w = self.canvas_mapa.winfo_width() or 600
        padding = 8
        max_por_fila = min(n_plazas, 10)
        filas = (n_plazas + max_por_fila - 1) // max_por_fila
        ancho_px = (w - 2 * padding) // max_por_fila - 4
        alto_px = 40

        plazas = db.obtener_plazas()
        estado_map = {p["numero"]: p for p in plazas}

        for i in range(n_plazas):
            fila = i // max_por_fila
            col  = i % max_por_fila
            x1 = padding + col * (ancho_px + 4)
            y1 = padding + fila * (alto_px + 4)
            x2 = x1 + ancho_px
            y2 = y1 + alto_px

            numero = i + 1
            info = estado_map.get(numero, {})
            color = COLOR_LIBRE if info.get("estado") == "libre" else COLOR_OCUPADA
            placa = info.get("vehiculo_placa") or ""

            rect = self.canvas_mapa.create_rectangle(
                x1, y1, x2, y2, fill=color, outline=COLOR_BG, width=2
            )
            lbl_num = self.canvas_mapa.create_text(
                (x1 + x2) // 2, y1 + 10,
                text=f"P{numero}", font=("Consolas", 8, "bold"),
                fill=COLOR_TEXTO_PZ
            )
            lbl_placa = self.canvas_mapa.create_text(
                (x1 + x2) // 2, y1 + 25,
                text=placa[:7], font=("Consolas", 7),
                fill=COLOR_TEXTO_PZ
            )
            self._plaza_rects[numero] = rect
            self._plaza_labels[numero] = lbl_placa

    def _actualizar_mapa(self):
        """Refresca colores y placas del mapa existente."""
        plazas = db.obtener_plazas()
        for p in plazas:
            numero = p["numero"]
            if numero not in self._plaza_rects:
                continue
            color = COLOR_LIBRE if p["estado"] == "libre" else COLOR_OCUPADA
            self.canvas_mapa.itemconfig(self._plaza_rects[numero], fill=color)
            placa = (p.get("vehiculo_placa") or "")[:7]
            self.canvas_mapa.itemconfig(self._plaza_labels[numero], text=placa)

    # ── Actualización de contadores ───────────────────────────────────────────

    def _actualizar_contadores(self):
        datos = db.contar_plazas()
        self.lbl_total.config(text=str(datos["total"]))
        self.lbl_libres.config(text=str(datos["libres"]))
        self.lbl_ocupados.config(text=str(datos["ocupadas"]))

        en_espera = sum(
            1 for v in db.obtener_vehiculos_activos() if v["estado"] == "esperando"
        )
        self.lbl_espera.config(text=str(en_espera))
        self.lbl_threads.config(text=str(self.simulacion.hilos_activos()))

    def _actualizar_tabla(self):
        """Recarga la tabla de vehículos desde la BD."""
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        vehiculos = db.obtener_todos_vehiculos()
        for v in vehiculos:
            plaza = v.get("plaza_id") or "-"
            tiempo = f"{v['tiempo_estacionado']:.1f}" if v["tiempo_estacionado"] else "-"
            tag = v["estado"]
            self.tabla.insert("", "end",
                              values=(v["placa"], v["estado"], plaza,
                                      v["hora_ingreso"] or "-", tiempo),
                              tags=(tag,))

    def _actualizar_metricas(self):
        atendidos = db.contar_atendidos()
        t_prom = db.tiempo_promedio_estacionado()
        datos = db.contar_plazas()
        uso = met.utilizacion(datos["ocupadas"], datos["total"])

        self.lbl_atendidos.config(text=str(atendidos))
        self.lbl_t_promedio.config(text=f"{t_prom:.1f}")
        self.lbl_uso.config(text=f"{uso:.1f}%")

    # ── Log de eventos ────────────────────────────────────────────────────────

    def _log(self, mensaje: str, nivel: str = "info"):
        self.txt_log.config(state="normal")
        tag = nivel if nivel in LOG_COLORES else "info"
        self.txt_log.insert("end", mensaje + "\n", tag)
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    # ── Procesamiento de la cola (hilo principal) ─────────────────────────────

    def _procesar_cola(self):
        """
        Consume mensajes de gui_queue cada 100ms.
        Este método corre SIEMPRE en el hilo principal de Tkinter.
        Los hilos secundarios SOLO ponen mensajes en la cola —
        nunca tocan widgets directamente.
        """
        try:
            while True:
                msg = self.gui_queue.get_nowait()
                self._manejar_mensaje(msg)
        except queue.Empty:
            pass
        finally:
            # Re-agendar para el siguiente ciclo (100ms)
            self.root.after(100, self._procesar_cola)

    def _manejar_mensaje(self, msg: dict):
        tipo = msg.get("tipo", "")
        nivel = msg.get("nivel", "info")
        mensaje = msg.get("mensaje", "")

        if mensaje:
            self._log(mensaje, nivel)

        if tipo in ("ingreso", "salida", "nuevo_vehiculo",
                    "actualizar_estado", "simulacion_terminada"):
            self._actualizar_contadores()
            self._actualizar_tabla()
            self._actualizar_mapa()
            self._actualizar_metricas()

        if tipo == "simulacion_terminada":
            self._log("─── Simulación finalizada ───", "info")

    # ── Callbacks de botones ──────────────────────────────────────────────────

    def _cb_iniciar(self):
        try:
            n_plazas   = int(self.spin_plazas.get())
            n_vehiculos = int(self.spin_vehiculos.get())
            t_min      = float(self.spin_tmin.get())
            t_max      = float(self.spin_tmax.get())
        except ValueError:
            messagebox.showerror("Error", "Valores de configuración inválidos.")
            return

        if t_min >= t_max:
            messagebox.showerror("Error", "T.min debe ser menor que T.max.")
            return

        if not self.simulacion._stop_event.is_set():
            messagebox.showinfo("Info", "Ya hay una simulación activa. Detén primero.")
            return

        # Reiniciar BD y parqueadero
        db.inicializar_parqueadero(n_plazas)
        self.parqueadero.reiniciar(n_plazas)
        self._n_plazas = n_plazas
        self._dibujar_mapa(n_plazas)
        self._actualizar_contadores()
        self._actualizar_tabla()
        self._log(f"─── Iniciando simulación: {n_plazas} plazas, {n_vehiculos} vehículos ───", "info")

        self.simulacion.iniciar(n_vehiculos, t_min, t_max,
                                intervalo_llegada=1.5)

    def _cb_agregar(self):
        """Agrega un vehículo manual a la simulación activa."""
        import random, string
        placa = ("".join(random.choices(string.ascii_uppercase, k=3)) +
                 "-" + "".join(random.choices(string.digits, k=3)))

        from simulacion import VehiculoThread
        hilo = VehiculoThread(
            placa, self.parqueadero, self.gui_queue,
            self.simulacion._stop_event,
            float(self.spin_tmin.get()), float(self.spin_tmax.get())
        )
        hilo.start()
        self.simulacion._hilos.append(hilo)

    def _cb_detener(self):
        self.simulacion.detener()
        self._log("─── Simulación detenida por el usuario ───", "salida")

    def _cb_reiniciar(self):
        try:
            n_plazas   = int(self.spin_plazas.get())
            n_vehiculos = int(self.spin_vehiculos.get())
            t_min      = float(self.spin_tmin.get())
            t_max      = float(self.spin_tmax.get())
        except ValueError:
            messagebox.showerror("Error", "Valores de configuración inválidos.")
            return

        self._log("─── Reiniciando simulación ───", "info")
        self._n_plazas = n_plazas

        self.simulacion.reiniciar(n_plazas, n_vehiculos, t_min, t_max,
                                  intervalo_llegada=1.5)
        self._dibujar_mapa(n_plazas)

    def _cb_exportar(self):
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="eventos_parqueadero.csv"
        )
        if ruta:
            ok, msg = met.exportar_csv(ruta)
            if ok:
                messagebox.showinfo("Exportado", f"Archivo guardado:\n{ruta}")
            else:
                messagebox.showerror("Error", msg)
