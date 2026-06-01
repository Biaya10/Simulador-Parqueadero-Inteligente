"""
database.py — Capa de acceso a datos (SQLite)

Responsabilidades:
  - Conexión única compartida con check_same_thread=False
  - Creación de tablas con relaciones (FK)
  - CRUD de vehículos, plazas y eventos
  - Un threading.Lock protege TODOS los accesos a SQLite
    (SQLite admite lectura concurrente, pero escritura exclusiva)

Analogía SO: este módulo es el "gestor de memoria" — administra
el recurso compartido en disco de forma segura.
"""

import sqlite3
import threading
import os
from datetime import datetime

# ── Ruta de la BD junto al script principal ──────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "parqueadero.db")

# ── Conexión global y lock de BD ─────────────────────────────────────────────
# check_same_thread=False: permite que múltiples hilos usen la misma conexión.
# El Lock propio (_db_lock) garantiza exclusión mutua en las escrituras.
_conn: sqlite3.Connection | None = None
_db_lock = threading.Lock()


def conectar() -> sqlite3.Connection:
    """Retorna la conexión global; la crea si no existe."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row   # acceso por nombre de columna
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")  # mejor concurrencia
    return _conn


def cerrar():
    """Cierra la conexión global."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None


# ── Creación de tablas ────────────────────────────────────────────────────────

def crear_tablas():
    """Crea las 4 tablas si no existen. Idempotente."""
    conn = conectar()
    with _db_lock:
        conn.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS parqueadero (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                nombre          TEXT    NOT NULL DEFAULT 'Parqueadero Central',
                cantidad_plazas INTEGER NOT NULL DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS plazas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                numero         INTEGER NOT NULL,
                estado         TEXT    NOT NULL DEFAULT 'libre',
                parqueadero_id INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (parqueadero_id) REFERENCES parqueadero(id)
            );

            CREATE TABLE IF NOT EXISTS vehiculos (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                placa              TEXT    NOT NULL UNIQUE,
                estado             TEXT    NOT NULL DEFAULT 'esperando',
                hora_ingreso       TEXT,
                hora_salida        TEXT,
                tiempo_estacionado REAL    DEFAULT 0.0,
                plaza_id           INTEGER,
                FOREIGN KEY (plaza_id) REFERENCES plazas(id)
            );

            CREATE TABLE IF NOT EXISTS eventos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                tipo        TEXT    NOT NULL,
                vehiculo_id INTEGER,
                detalle     TEXT,
                FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
            );
        """)
        conn.commit()


# ── Inicialización del parqueadero ────────────────────────────────────────────

def inicializar_parqueadero(n_plazas: int = 5, nombre: str = "Parqueadero Central"):
    """
    Inserta (o reemplaza) la fila única del parqueadero y crea sus plazas.Llamar antes de cada simulación para reiniciar el estado.
    """
    conn = conectar()
    with _db_lock:
        conn.execute("DELETE FROM eventos")
        conn.execute("DELETE FROM vehiculos")
        conn.execute("DELETE FROM plazas")
        conn.execute("DELETE FROM parqueadero")
        conn.execute(
            "INSERT INTO parqueadero (id, nombre, cantidad_plazas) VALUES (1, ?, ?)",
            (nombre, n_plazas)
        )
        for i in range(1, n_plazas + 1):
            conn.execute(
                "INSERT INTO plazas (numero, estado, parqueadero_id) VALUES (?, 'libre', 1)",
                (i,)
            )
        conn.commit()


# ── CRUD de Vehículos ─────────────────────────────────────────────────────────

def insertar_vehiculo(placa: str) -> int:
    """Inserta un vehículo en estado 'esperando'. Retorna su id."""
    conn = conectar()
    with _db_lock:
        cur = conn.execute(
            "INSERT OR IGNORE INTO vehiculos (placa, estado) VALUES (?, 'esperando')",
            (placa,)
        )
        conn.commit()
        return cur.lastrowid


def buscar_vehiculo(placa: str) -> dict | None:
    """Retorna el vehículo como dict, o None si no existe."""
    conn = conectar()
    with _db_lock:
        row = conn.execute(
            "SELECT * FROM vehiculos WHERE placa = ?", (placa,)
        ).fetchone()
    return dict(row) if row else None


def obtener_todos_vehiculos() -> list[dict]:
    """Lista todos los vehículos ordenados por id DESC."""
    conn = conectar()
    with _db_lock:
        rows = conn.execute(
            "SELECT * FROM vehiculos ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def obtener_vehiculos_activos() -> list[dict]:
    """Vehículos en estado 'esperando' o 'estacionado'."""
    conn = conectar()
    with _db_lock:
        rows = conn.execute(
            "SELECT * FROM vehiculos WHERE estado IN ('esperando', 'estacionado') ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def actualizar_ingreso(vehiculo_id: int, plaza_id: int, hora_ingreso: str):
    """Marca el vehículo como 'estacionado' y le asigna la plaza."""
    conn = conectar()
    with _db_lock:
        conn.execute(
            """UPDATE vehiculos
               SET estado = 'estacionado', plaza_id = ?, hora_ingreso = ?
               WHERE id = ?""",
            (plaza_id, hora_ingreso, vehiculo_id)
        )
        conn.execute(
            "UPDATE plazas SET estado = 'ocupada' WHERE id = ?",
            (plaza_id,)
        )
        conn.commit()


def actualizar_salida(vehiculo_id: int, plaza_id: int, hora_salida: str, tiempo: float):
    """Marca el vehículo como 'salido' y libera la plaza."""
    conn = conectar()
    with _db_lock:
        conn.execute(
            """UPDATE vehiculos
               SET estado = 'salido', hora_salida = ?, tiempo_estacionado = ?, plaza_id = NULL
               WHERE id = ?""",
            (hora_salida, tiempo, vehiculo_id)
        )
        conn.execute(
            "UPDATE plazas SET estado = 'libre' WHERE id = ?",
            (plaza_id,)
        )
        conn.commit()


def eliminar_vehiculo(placa: str):
    """Elimina un vehículo por placa (solo si ya salió)."""
    conn = conectar()
    with _db_lock:
        conn.execute("DELETE FROM vehiculos WHERE placa = ?", (placa,))
        conn.commit()


# ── Plazas ────────────────────────────────────────────────────────────────────

def obtener_plazas() -> list[dict]:
    """Retorna todas las plazas con su estado actual."""
    conn = conectar()
    with _db_lock:
        rows = conn.execute(
            """SELECT p.id, p.numero, p.estado,
                      v.placa as vehiculo_placa
               FROM plazas p
               LEFT JOIN vehiculos v ON v.plaza_id = p.id AND v.estado = 'estacionado'
               ORDER BY p.numero"""
        ).fetchall()
    return [dict(r) for r in rows]


def obtener_plaza_libre() -> dict | None:
    """Retorna la primera plaza libre disponible, o None."""
    conn = conectar()
    with _db_lock:
        row = conn.execute(
            "SELECT * FROM plazas WHERE estado = 'libre' ORDER BY numero LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def contar_plazas() -> dict:
    """Retorna {'total': N, 'libres': X, 'ocupadas': Y}."""
    conn = conectar()
    with _db_lock:
        row = conn.execute(
            """SELECT cantidad_plazas as total,
                      (SELECT COUNT(*) FROM plazas WHERE estado = 'libre')  as libres,
                      (SELECT COUNT(*) FROM plazas WHERE estado = 'ocupada') as ocupadas
               FROM parqueadero WHERE id = 1"""
        ).fetchone()
    return dict(row) if row else {"total": 0, "libres": 0, "ocupadas": 0}


# ── Eventos ───────────────────────────────────────────────────────────────────

def registrar_evento(tipo: str, vehiculo_id: int | None, detalle: str = ""):
    """Inserta un evento en la bitácora."""
    conn = conectar()
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with _db_lock:
        conn.execute(
            "INSERT INTO eventos (timestamp, tipo, vehiculo_id, detalle) VALUES (?, ?, ?, ?)",
            (ts, tipo, vehiculo_id, detalle)
        )
        conn.commit()


def obtener_eventos(limite: int = 100) -> list[dict]:
    """Retorna los últimos N eventos con placa incluida."""
    conn = conectar()
    with _db_lock:
        rows = conn.execute(
            """SELECT e.id, e.timestamp, e.tipo, e.detalle,
                      v.placa as placa
               FROM eventos e
               LEFT JOIN vehiculos v ON v.id = e.vehiculo_id
               ORDER BY e.id DESC LIMIT ?""",
            (limite,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Métricas rápidas ──────────────────────────────────────────────────────────

def contar_atendidos() -> int:
    conn = conectar()
    with _db_lock:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM vehiculos WHERE estado = 'salido'"
        ).fetchone()
    return row["n"] if row else 0


def tiempo_promedio_estacionado() -> float:
    """Tiempo promedio en segundos de los vehículos que ya salieron."""
    conn = conectar()
    with _db_lock:
        row = conn.execute(
            "SELECT AVG(tiempo_estacionado) as avg FROM vehiculos WHERE estado = 'salido'"
        ).fetchone()
    val = row["avg"] if row else None
    return round(val, 2) if val else 0.0
