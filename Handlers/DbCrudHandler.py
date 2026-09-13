import sqlite3


DB_PATH = "/home/Night/github/ApiMvpHack/ProyectDb.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ejecutar_sql(query: str) -> str:
    r"""Ejecuta SQL arbitrario y retorna los resultados formateados.

    Usa esta herramienta para ejecutar consultas SQL directas sobre la base de datos ProyectDb.
    Ideal para SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE.
    El resultado se devuelve formateado como tabla de texto.
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            if not rows:
                return "La consulta no devolvio resultados."
            headers = list(rows[0].keys())
            lines = [" | ".join(headers)]
            lines.append("-" * len(lines[0]))
            for row in rows:
                lines.append(" | ".join(str(row[h]) for h in headers))
            return "\n".join(lines)
        else:
            conn.commit()
            return f"OK. Filas afectadas: {cursor.rowcount}"
    except Exception as e:
        return f"Error SQL: {e}"
    finally:
        conn.close()


def listar_tablas() -> str:
    r"""Lista todas las tablas de la base de datos con sus columnas y tipos."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tablas = [row["name"] for row in cursor.fetchall()]
        if not tablas:
            return "No hay tablas en la base de datos."

        lines = ["=== Tablas en ProyectDb ==="]
        for tabla in tablas:
            cols = conn.execute(f"PRAGMA table_info({tabla})").fetchall()
            col_info = ", ".join(f"{c['name']} ({c['type']})" for c in cols)
            lines.append(f"\n{tabla}: {col_info}")
        return "\n".join(lines)
    finally:
        conn.close()


def describir_tabla(nombre: str) -> str:
    r"""Muestra el schema completo de una tabla (columnas, tipos, constraints)."""
    conn = _get_conn()
    try:
        cursor = conn.execute(f"PRAGMA table_info({nombre})")
        cols = cursor.fetchall()
        if not cols:
            return f"La tabla '{nombre}' no existe."
        lines = [
            f"=== Schema de '{nombre}' ===",
            f"{'#':<3} {'Nombre':<20} {'Tipo':<15} {'Nullable':<10} {'Default':<10}"
        ]
        for i, col in enumerate(cols):
            lines.append(
                f"{i+1:<3} {col['name']:<20} {col['type']:<15} "
                f"{'YES' if col['notnull'] else 'NO':<10} {str(col['dflt_value']):<10}"
            )
        return "\n".join(lines)
    finally:
        conn.close()


def crear_tabla(nombre: str, columnas: dict) -> str:
    r"""Crea una tabla nueva en la base de datos.

    Args:
        nombre: Nombre de la tabla (solo letras, numeros, guiones bajos).
        columnas: Diccionario con nombre_columna: tipo_sql. Ejemplo: {"nombre": "TEXT", "edad": "INTEGER"}

    Usa esta herramienta cuando el usuario pida crear una nueva tabla en la base de datos.
    """
    conn = _get_conn()
    try:
        cols_sql = ", ".join(f"{k} {v}" for k, v in columnas.items())
        query = f"CREATE TABLE IF NOT EXISTS {nombre} ({cols_sql})"
        conn.execute(query)
        conn.commit()
        return f"Tabla '{nombre}' creada correctamente."
    except Exception as e:
        return f"Error creando tabla: {e}"
    finally:
        conn.close()


def borrar_tabla(nombre: str) -> str:
    r"""Elimina una tabla completa de la base de datos.

    WARNING: Esto elimina TODOS los datos de la tabla de forma permanente.
    Solo usa esta herramienta si el usuario esta seguro de lo que hace.
    """
    conn = _get_conn()
    try:
        conn.execute(f"DROP TABLE IF EXISTS {nombre}")
        conn.commit()
        return f"Tabla '{nombre}' eliminada."
    except Exception as e:
        return f"Error eliminando tabla: {e}"
    finally:
        conn.close()
