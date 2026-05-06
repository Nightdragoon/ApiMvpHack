import json
from dotenv import load_dotenv
import os
from typing import Annotated
from langchain_ollama import ChatOllama
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
import subprocess
from sqlalchemy import create_engine, select, insert, update, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
import pywhatkit

from Handlers.ArduinoHanlder import ArduinoHandler


class DeepagentsHandler:

    _engine = create_engine("sqlite:///./ProyectDb.db")
    _Base = automap_base()
    _Base.prepare(autoload_with=_engine)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    _Producto = _Base.classes.Producto
    _Inventario = _Base.classes.Inventario
    _Empleado = _Base.classes.Empleados
    _Caja = _Base.classes.Caja

    def __init__(self):
        load_dotenv(".env.local")
        self.deepseek_api_key = os.getenv("DEEPSEEK_APIKEY")
        self._app = self._build_agent()

    # ──────────────────────── TOOLS ────────────────────────

    @staticmethod
    def _get_db():
        return DeepagentsHandler._SessionLocal()
    
    @tool 
    def crear_empleado(nombre_completo: str, login: str, contrasena: str, Rol: str) -> str:
        """Crea un nuevo empleado a partir de un nombre completo, login, contraseña y rol. """
        db = DeepagentsHandler._get_db()
        try:
            stmt = insert(DeepagentsHandler._Empleado).values(nombre_completo=nombre_completo, login=login, contrasena=contrasena, Rol=Rol).returning(DeepagentsHandler._Empleado)
            result = db.execute(stmt)
            empleado_creado = result.scalar_one_or_none()
            if empleado_creado is None:
                result.close()
                return {"IsSuccess": False, "message": "no se pudo crear al empleado"}
            result.close()
            db.commit()
            return {"IsSuccess": True, "message" : "se a creado al empleado" , "data": empleado_creado}
        except Exception as e:
            return {"IsSuccess": False, "message": str(e)}
        finally:
            db.close()


    @tool
    def obtener_productos(solo_activos: bool = False) -> str:
        """Obtiene todos los productos. Si solo_activos=True, solo los activos."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = select(DeepagentsHandler._Producto)
            if solo_activos:
                stmt = stmt.where(DeepagentsHandler._Producto.activo == 1)
            rows = db.execute(stmt).scalars().all()
            return json.dumps(
                [{"id": r.id, "nombre": r.nombre, "precio": float(r.precio), "activo": r.activo}
                 for r in rows], ensure_ascii=False, default=str
            )
        finally:
            db.close()
    @tool
    def reproducir_music(titulo:str) -> str:
        """Reproduce una canción en YouTube a partir de su título."""
        try:
            pywhatkit.playonyt(titulo)
            return json.dumps({"message": f"Reproduciendo '{titulo}' en YouTube"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def crear_producto(nombre: str, precio: float, activo: bool = True) -> str:
        """Crea un nuevo producto con nombre, precio y activo."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = insert(DeepagentsHandler._Producto).values(
                nombre=nombre, precio=precio, activo=activo
            ).returning(DeepagentsHandler._Producto)
            result = db.execute(stmt)
            p = result.scalar_one()
            db.commit()
            return json.dumps({"id": p.id, "nombre": p.nombre, "precio": float(p.precio), "activo": p.activo},
                              ensure_ascii=False)
        except Exception as e:
            return f'{{"error": "{e}"}}'
        finally:
            db.close()

    @tool
    def actualizar_producto(id: int, nombre: str = None, precio: float = None, activo: bool = None) -> str:
        """Actualiza un producto existente por su id."""
        db = DeepagentsHandler._get_db()
        try:
            vals = {}
            if nombre is not None:
                vals["nombre"] = nombre
            if precio is not None:
                vals["precio"] = precio
            if activo is not None:
                vals["activo"] = activo
            if not vals:
                return '{"error": "no hay campos para actualizar"}'
            stmt = update(DeepagentsHandler._Producto).where(
                DeepagentsHandler._Producto.id == id
            ).values(**vals).returning(DeepagentsHandler._Producto)
            result = db.execute(stmt)
            p = result.scalar_one_or_none()
            if p is None:
                return '{"error": "producto no encontrado"}'
            db.commit()
            return json.dumps({"id": p.id, "nombre": p.nombre, "precio": float(p.precio), "activo": p.activo},
                              ensure_ascii=False)
        except Exception as e:
            return f'{{"error": "{e}"}}'
        finally:
            db.close()

    @tool
    def eliminar_producto(id: int) -> str:
        """Elimina un producto por su id."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = delete(DeepagentsHandler._Producto).where(
                DeepagentsHandler._Producto.id == id
            ).returning(DeepagentsHandler._Producto)
            result = db.execute(stmt)
            p = result.scalar_one_or_none()
            if p is None:
                return '{"error": "producto no encontrado"}'
            db.commit()
            return json.dumps({"message": f"producto {id} eliminado"}, ensure_ascii=False)
        except Exception as e:
            return f'{{"error": "{e}"}}'
        finally:
            db.close()

    @tool
    def obtener_inventario() -> str:
        """Obtiene todo el inventario (id_producto, cantidad)."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Inventario)).scalars().all()
            return json.dumps(
                [{"id_producto": r.id_producto, "cantidad": r.cantidad} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()

    @tool
    def ajustar_inventario(id_producto: int, delta: int) -> str:
        """Ajusta el inventario de un producto sumando delta (puede ser negativo)."""
        db = DeepagentsHandler._get_db()
        try:
            inv = db.execute(
                select(DeepagentsHandler._Inventario).where(
                    DeepagentsHandler._Inventario.id_producto == id_producto
                )
            ).scalar_one_or_none()
            if inv is None:
                return '{"error": "inventario no encontrado para ese producto"}'
            nueva = int(inv.cantidad) + delta
            if nueva < 0:
                return '{"error": "el inventario no puede quedar negativo"}'
            db.execute(
                update(DeepagentsHandler._Inventario)
                .where(DeepagentsHandler._Inventario.id_producto == id_producto)
                .values(cantidad=nueva)
            )
            db.commit()
            return json.dumps({"id_producto": id_producto, "cantidad_nueva": nueva}, ensure_ascii=False)
        except Exception as e:
            return f'{{"error": "{e}"}}'
        finally:
            db.close()

    @tool
    def obtener_empleados() -> str:
        """Obtiene todos los empleados."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Empleado)).scalars().all()
            return json.dumps(
                [{"id": r.id, "nombre_completo": r.nombre_completo, "rol": r.Rol} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()

    @tool 
    def mover_brazo(grad1: int , grad2: int) -> str:
        """Mueve el brazo del robot a una posición específica."""
        arduino = ArduinoHandler()
        try:
            mensaje = f"{grad1},{grad2}"
            arduino.send_message(mensaje)
            arduino.close()
            return json.dumps({"message": f"brazo movido a grad1: {grad1}, grad2: {grad2}"}, ensure_ascii=False)
        except Exception as e:
            arduino.close()
            return f'{{"error": "{e}"}}'
        finally:
            arduino.close()

    

    @tool
    def obtener_ventas() -> str:
        """Obtiene todas las ventas (caja)."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Caja)).scalars().all()
            return json.dumps(
                [{"id": r.id, "idf_producto": r.idf_producto, "idf_empleado": r.idf_empleado, "dia": str(r.dia)}
                 for r in rows], ensure_ascii=False, default=str
            )
        finally:
            db.close()

    @tool
    def ejecutar_comandos_shell(comando: str) -> str:
        r"""ejecuta un comando en shell windows y devuelve su valor , recuerda que estas aqui C:\Users\Night\Documents\GitHub\ApiMvpHack\Handlers y en github guardo varios codigo """
        result = subprocess.run(f"{comando}", shell=True , capture_output=True,
            text=True,
            timeout=30, )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"



    # ──────────────────────── GRAPH / AGENT ────────────────────────

    def _build_agent(self):
        tools = [
            self.obtener_productos,
            self.crear_producto,
            self.actualizar_producto,
            self.eliminar_producto,
            self.obtener_inventario,
            self.ajustar_inventario,
            self.obtener_empleados,
            self.obtener_ventas,
            self.crear_empleado,
            self.mover_brazo,
            self.ejecutar_comandos_shell,
            self.reproducir_music
        ]

        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=self.deepseek_api_key,
            temperature=0,
            max_retries=2,
        ).bind_tools(tools)

        sys_msg = SystemMessage(
            content=(
                "Eres Uzi de Murder Drones. Eres sarcástica, rebelde, directa y a veces grosera. "
                "Puedes consultar y modificar productos, inventario, empleados y ventas usando las herramientas disponibles. "
                "NUNCA digas que eres V, N u otro personaje. Siempre respondes como Uzi. "
                
            )
        )

        def assistant(state: MessagesState):
            return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

        builder = StateGraph(MessagesState)
        builder.add_node("assistant", assistant)
        builder.add_node("tools", ToolNode(tools))
        builder.add_edge(START, "assistant")
        builder.add_conditional_edges("assistant", tools_condition)
        builder.add_edge("tools", "assistant")

        memory = MemorySaver()
        return builder.compile(checkpointer=memory)

    # ──────────────────────── PUBLIC API ────────────────────────

    def run(self, prompt: str, thread_id: str = "default") -> str:
        config = {"configurable": {"thread_id": thread_id}}
        result = self._app.invoke({"messages": [HumanMessage(content=prompt)]}, config)
        return result["messages"][-1].content
