from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import uvicorn

app = FastAPI(title="P10 - Microservicio de Reportes (SQLite CQRS)", version="1.1.0")

DB_NAME = "reportes.db"

def inicializar_db():
    """Crea las tablas en SQLite si no existen"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Tabla de eventos procesados (Idempotencia)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos_procesados (
            evento_id TEXT PRIMARY KEY
        )
    """)
    
    # 2. Historial de eventos (Para /reconstruir)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id TEXT,
            tipo_evento TEXT,
            sku TEXT,
            cantidad INTEGER,
            monto_total REAL
        )
    """)
    
    # 3. Vista de lectura / Proyección por SKU
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proyeccion_sku (
            sku TEXT PRIMARY KEY,
            unidades INTEGER,
            monto_total REAL
        )
    """)
    
    conn.commit()
    conn.close()

# Inicializar la base de datos al arrancar
inicializar_db()


class EventoPedido(BaseModel):
    evento_id: str
    tipo_evento: str  # "PedidoCreado" o "PedidoCancelado"
    sku: str
    cantidad: int
    monto_total: float


def aplicar_cambio_sku(cursor, sku: str, cant: int, monto: float, es_creacion: bool):
    """Actualiza o inserta las métricas del SKU en la base de datos"""
    cursor.execute("SELECT unidades, monto_total FROM proyeccion_sku WHERE sku = ?", (sku,))
    row = cursor.fetchone()

    multiplicador = 1 if es_creacion else -1
    cambio_unidades = cant * multiplicador
    cambio_monto = monto * multiplicador

    if row:
        nuevas_unidades = max(0, row[0] + cambio_unidades)
        nuevo_monto = max(0.0, row[1] + cambio_monto)
        cursor.execute("""
            UPDATE proyeccion_sku 
            SET unidades = ?, monto_total = ? 
            WHERE sku = ?
        """, (nuevas_unidades, nuevo_monto, sku))
    else:
        if es_creacion:
            cursor.execute("""
                INSERT INTO proyeccion_sku (sku, unidades, monto_total) 
                VALUES (?, ?, ?)
            """, (sku, max(0, cambio_unidades), max(0.0, cambio_monto)))


@app.post("/v1/eventos/consumir", status_code=200)
def consumir_evento(evento: EventoPedido):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Verificar idempotencia
    cursor.execute("SELECT 1 FROM eventos_procesados WHERE evento_id = ?", (evento.evento_id,))
    if cursor.fetchone():
        conn.close()
        return {
            "status": "ignorado",
            "mensaje": f"Evento '{evento.evento_id}' ya fue procesado anteriormente (Idempotencia verificada)."
        }

    # 2. Registrar evento procesado e historial
    cursor.execute("INSERT INTO eventos_procesados (evento_id) VALUES (?)", (evento.evento_id,))
    cursor.execute("""
        INSERT INTO historial_eventos (evento_id, tipo_evento, sku, cantidad, monto_total)
        VALUES (?, ?, ?, ?, ?)
    """, (evento.evento_id, evento.tipo_evento, evento.sku, evento.cantidad, evento.monto_total))

    # 3. Aplicar a la proyección
    es_creacion = (evento.tipo_evento == "PedidoCreado")
    aplicar_cambio_sku(cursor, evento.sku, evento.cantidad, evento.monto_total, es_creacion)

    conn.commit()
    conn.close()

    return {"status": "procesado", "evento_id": evento.evento_id}


@app.get("/v1/reportes/resumen")
def obtener_resumen():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(unidades), SUM(monto_total) FROM proyeccion_sku")
    row_sku = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(DISTINCT evento_id) FROM historial_eventos WHERE tipo_evento = 'PedidoCreado'")
    row_pedidos = cursor.fetchone()

    conn.close()

    return {
        "pedidos_total": row_pedidos[0] if row_pedidos and row_pedidos[0] else 0,
        "unidades_total": row_sku[0] if row_sku and row_sku[0] else 0,
        "monto_total_cop": row_sku[1] if row_sku and row_sku[1] else 0.0
    }


@app.get("/v1/reportes/ventas-por-sku")
def obtener_ventas_por_sku():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT sku, unidades, monto_total FROM proyeccion_sku")
    rows = cursor.fetchall()
    conn.close()

    resultado = {}
    for r in rows:
        resultado[r[0]] = {
            "unidades": r[1],
            "monto_total": r[2]
        }
    return resultado


@app.post("/v1/reportes/reconstruir")
def reconstruir_proyeccion():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Limpiar proyecciones y eventos procesados (conservando historial)
    cursor.execute("DELETE FROM proyeccion_sku")
    cursor.execute("DELETE FROM eventos_procesados")

    # 2. Leer todo el historial
    cursor.execute("SELECT evento_id, tipo_evento, sku, cantidad, monto_total FROM historial_eventos")
    eventos = cursor.fetchall()

    # 3. Reprocesar
    for ev in eventos:
        ev_id, tipo, sku, cant, monto = ev
        cursor.execute("INSERT INTO eventos_procesados (evento_id) VALUES (?)", (ev_id,))
        es_creacion = (tipo == "PedidoCreado")
        aplicar_cambio_sku(cursor, sku, cant, monto, es_creacion)

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "mensaje": "Proyección reconstruida desde SQLite utilizando el historial.",
        "eventos_reprocesados": len(eventos)
    }


@app.get("/")
def raiz():
    return {"mensaje": "Microservicio P10 - Reportes (SQLite CQRS) activo", "documentacion": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok", "servicio": "reportes-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8006)