# README — Simulador de Parqueadero Inteligente

**Proyecto Final con Concurrencia y Sincronización en Python**

## Descripción General

Un simulador que demuestra conceptos fundamentales de Sistemas Operativos:
- **Concurrencia:** Múltiples vehículos (threads) compitiendo simultáneamente
- **Sincronización:** Semáforos y Locks para coordinar el acceso a recursos
- **Recursos limitados:** Plazas de parqueo (semaphores de conteo)
- **Race conditions:** Cómo evitarlas con exclusión mutua
- **IPC:** Comunicación segura thread → GUI con `queue.Queue`

## Capturas de Pantalla

### Interfaz Principal
<img width="1249" height="905" alt="interfaz_principal" src="https://github.com/user-attachments/assets/76e7adc6-52ae-4f42-9fe7-7b1ce1c83ed2" />

### Simulación en ejecución
<img width="1233" height="888" alt="simulacion" src="https://github.com/user-attachments/assets/330c7331-959f-4662-ac87-6bb6690139c3" />

## Contenido del Proyecto

```
ParqueaderoInteligente/
├── main.py              # Punto de entrada (abre la GUI)
├── database.py          # SQLite: tablas, CRUD, Lock de BD
├── parqueadero.py       # Lógica: Semaphore + Lock + ingresar/salir
├── simulacion.py        # Motor: VehiculoThread + Simulacion
├── gui.py               # Interfaz Tkinter completa
├── metricas.py          # Estadísticas + exportar CSV
├── demo.py              # Script de demostración (sin GUI)
├── parqueadero.db       # Base de datos (se genera automáticamente)
├── logs/                # Carpeta para exportar CSVs
├── INFORME.md           # Informe académico completo
├── ARQUITECTURA.md      # Documentación técnica de la arquitectura
├── README.md            # Este archivo
└── requirements.txt     # Dependencias (solo stdlib)
```

## Cómo ejecutar el proyecto

### Opción 1: Ejecutar Interfaz Gráfica 

```bash
python main.py
```

**La aplicación abrirá una interfaz donde es posible:**
- iniciar simulación
- detener simulación
- reiniciar
- exportar eventos
- visualizar ocupación del parqueadero

## Funcionalidades principales
- Simulación concurrente de vehículos
- Control de acceso mediante semáforos
- Exclusión mutua utilizando locks
- Registro de eventos en SQLite
- Exportación de eventos a CSV
- Visualización en tiempo real de plazas ocupadas
- Cola de espera de vehículos
 
 ### En interfaz se observa 
- Mapa visual de plazas (verde=libre, rojo=ocupada)
- Tabla de vehículos con su estado
- Log en tiempo real de eventos
- Métricas: atendidos, tiempo promedio, uso %
- Controles: iniciar, detener, reiniciar, exportar

### Opción 2: Demostración en consola

```bash
python demo.py
```

**Salida:**
```
[14:32:15] SRN-261 llegó al parqueadero
[14:32:16] SRN-261 esperando... (3 libres)
[14:32:17] SRN-261 estacionó en Plaza 1
[14:32:20] SRN-261 salió de Plaza 1 (3.2s)
```

### Conceptos de Sistemas Operativos implementados
| **Elemento del Parqueadero** | **Concepto de SO** | **Explicación** |
|---|---|---|
| **Vehículo** | Proceso/Hilo | Entidad independiente que necesita un recurso |
| **Plaza de parqueo** | Recurso del sistema (CPU, memoria) | Recurso limitado y compartido |
| **Semáforo (contador)** | Semaphore de Dijkstra | Controla acceso a recursos finitos |
| **Caseta de registro** | Mutex / Lock | Garantiza acceso exclusivo a sección crítica |
| **Cola de espera** | Ready Queue del scheduler | Vehículos esperando oportunidad de entrar |
| **Bloqueo automático** | Blocking de procesos | Hilo se duerme hasta que recurso esté libre |


### Persistencia de datos

El sistema utiliza SQLite para almacenar:

- ingresos
- salidas
- eventos
- tiempos de permanencia

Además, los eventos pueden exportarse en formato CSV.



### Demostración:
▶ Video de funcionamiento:

https://youtu.be/c3ziUIjVpaA 


### Información Académica

Autora: Amanda Carolina Chindoy Muchavisoy

Proyecto desarrollado para la asignatura Arquitectura de Computadores y Sistemas Operativos.
