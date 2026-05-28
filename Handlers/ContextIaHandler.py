import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker


class ContextHandler:
    def __init__(self, db_path="sqlite:///./ProyectDb.db"):
        load_dotenv(".env.local")
        self.engine = create_engine(db_path)
        Base = automap_base()
        Base.prepare(autoload_with=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def guardar_mensaje(self, chat_id: str, rol: str, contenido: str):
        """Guarda un mensaje en el historial. rol = 'user' o 'assistant'"""
        with self.engine.connect() as conn:
            conn.execute(
                text("INSERT INTO historial (remitente, mensaje) VALUES (:rol, :contenido)"),
                {"rol": f"{chat_id}:{rol}", "contenido": contenido}
            )
            conn.commit()

    def obtener_historial(self, chat_id: str, limite: int = 20) -> list[dict]:
        """Obtiene los últimos N mensajes de un chat, del más antiguo al más reciente."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT remitente, mensaje FROM historial
                    WHERE remitente LIKE :patron
                    ORDER BY id DESC
                    LIMIT :limite
                """),
                {"patron": f"{chat_id}:%", "limite": limite}
            ).fetchall()
        result = []
        for remitente, mensaje in reversed(rows):
            rol = remitente.split(":", 1)[1]
            result.append({"rol": rol, "contenido": mensaje})
        return result

    def contar_mensajes(self, chat_id: str) -> int:
        """Cuenta los mensajes actuales en el historial para un chat."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM historial WHERE remitente LIKE :patron"),
                {"patron": f"{chat_id}:%"}
            ).scalar()
        return row or 0

    def eliminar_ultimos_n_mensajes(self, chat_id: str, n: int):
        """Elimina los últimos N mensajes del historial para un chat."""
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    DELETE FROM historial WHERE id IN (
                        SELECT id FROM historial
                        WHERE remitente LIKE :patron
                        ORDER BY id DESC
                        LIMIT :n
                    )
                """),
                {"patron": f"{chat_id}:%", "n": n}
            )
            conn.commit()

    def obtener_memoria_largoplazo(self, chat_id: str) -> str | None:
        """Obtiene la memoria de largo plazo acumulada para un chat."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT memoria FROM Memoria_Largoplazo WHERE chat_id = :chat_id"),
                {"chat_id": chat_id}
            ).scalar()
        return row if row else None

    def actualizar_memoria_largoplazo(self, chat_id: str, resumen: str):
        """Reemplaza la memoria de largo plazo para un chat con el nuevo resumen."""
        with self.engine.connect() as conn:
            conn.execute(
                text("DELETE FROM Memoria_Largoplazo WHERE chat_id = :chat_id"),
                {"chat_id": chat_id}
            )
            conn.execute(
                text("INSERT INTO Memoria_Largoplazo (chat_id, memoria) VALUES (:chat_id, :resumen)"),
                {"chat_id": chat_id, "resumen": resumen}
            )
            conn.commit()

    def limpiar_chat(self, chat_id: str):
        """Elimina todo el historial y la memoria de largo plazo de un chat específico."""
        with self.engine.connect() as conn:
            conn.execute(
                text("DELETE FROM historial WHERE remitente LIKE :patron"),
                {"patron": f"{chat_id}:%"}
            )
            conn.execute(
                text("DELETE FROM Memoria_Largoplazo WHERE chat_id = :chat_id"),
                {"chat_id": chat_id}
            )
            conn.commit()

    def limpiar_viejos(self, dias: int = 7):
        """Elimina mensajes más viejos que X días."""
        with self.engine.connect() as conn:
            conn.execute(
                text("DELETE FROM historial WHERE id NOT IN (SELECT id FROM historial ORDER BY id DESC LIMIT 1000)")
            )
            conn.commit()
            
    def obtener_todos_contactos(self) -> list[dict]:
        """Obtiene todos los contactos autorizados."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, number, nombre FROM Contactos_Autorizados")
            ).fetchall()
        return [{"id": row[0], "number": row[1], "nombre": row[2]} for row in rows]

    def buscar_contacto_por_nombre(self, nombre: str) -> list[dict]:
        """Busca contactos por nombre (búsqueda parcial)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, number, nombre FROM Contactos_Autorizados WHERE nombre LIKE :nombre"),
                {"nombre": f"%{nombre}%"}
            ).fetchall()
        return [{"id": row[0], "number": row[1], "nombre": row[2]} for row in rows]