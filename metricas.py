"""
metricas.py — Estadísticas y exportación de logs

Funciones puras que leen de la BD y calculan métricas.No dependen de threading; son llamadas desde el hilo principal.
"""

import csv
import os
from datetime import datetime
import database as db


def utilizacion(ocupados: int, total: int) -> float:
    """Porcentaje de utilización del parqueadero."""
    if total == 0:
        return 0.0
    return round((ocupados / total) * 100, 1)


def resumen() -> dict:
    """Retorna un dict con todas las métricas actuales."""
    datos = db.contar_plazas()
    return {
        "total_plazas":      datos["total"],
        "libres":            datos["libres"],
        "ocupadas":          datos["ocupadas"],
        "uso_pct":           utilizacion(datos["ocupadas"], datos["total"]),
        "atendidos":         db.contar_atendidos(),
        "t_promedio_s":      db.tiempo_promedio_estacionado(),
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def exportar_csv(ruta: str) -> tuple[bool, str]:
    """
    Exporta la tabla de eventos a un archivo CSV.
    Retorna (True, "") si OK, (False, mensaje_error) si falla.
    """
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True) if os.path.dirname(ruta) else None
        eventos = db.obtener_eventos(limite=10_000)
        if not eventos:
            return False, "No hay eventos para exportar."

        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "timestamp", "tipo",
                                                    "placa", "detalle"])
            writer.writeheader()
            writer.writerows(eventos)

        return True, ""
    except Exception as e:
        return False, str(e)
