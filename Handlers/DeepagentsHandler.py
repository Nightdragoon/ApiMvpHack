import json
from dotenv import load_dotenv
import os
import asyncio
from typing import Annotated
from langchain_ollama import ChatOllama
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
import subprocess
import requests
from sqlalchemy import create_engine, select, insert, update, delete
from sqlalchemy.orm import sessionmaker
from Handlers.ElevenLabsHandler import ElevenLabsHandler
import yagmail
from sqlalchemy.ext.automap import automap_base
import pygame
import pywhatkit
import email
from email import policy
import imaplib2
import base64
from Handlers.NotionHandler import NotionHandler

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
    _Contacto = _Base.classes.Contactos_Autorizados

    def __init__(self):
        load_dotenv(".env.local")
        self.deepseek_api_key = os.getenv("DEEPSEEK_APIKEY")
        self._app = self._build_agent()
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_pass = os.getenv("GMAIL_PASS")
        pygame.init()

    # ──────────────────────── TOOLS ────────────────────────

    @staticmethod
    def _get_db():
        return DeepagentsHandler._SessionLocal()
    
    
    @tool
    def crear_nota_notion(titulo: str, contenido: str) -> str:
        """Crea una nueva página en Notion con el título y contenido especificados."""
        notion = NotionHandler()
        result = notion.create_page(titulo, contenido)
        if result is None:
            return json.dumps({"error": "Error al crear la página en Notion"}, ensure_ascii=False)
        return json.dumps({"message": f"Página creada en Notion con título '{titulo}'"}, ensure_ascii=False)
    
    
    @tool
    def leer_emails() -> str:
        """Lee los emails de la cuenta configurada y devuelve una lista de asuntos, remitentes y body."""
        try:
            mail = imaplib2.IMAP4_SSL("imap.gmail.com")
            mail.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_PASS"))
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            email_list = []

            for num in messages[0].split()[-13:]:
                status, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1], policy=policy.default)
                from_ = str(msg["From"]) or ""
                subject = str(msg["Subject"]) or ""
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_content()
                            break
                else:
                    body = msg.get_content()
                email_list.append({"from": from_, "subject": subject, "body": body})

            mail.logout()
            return json.dumps(email_list, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        
        
    @tool
    def enviar_whatsapp(numero: str, mensaje: str) -> str:
        """Envía un mensaje de WhatsApp al número especificado usando request."""
        try:
            url = "http://localhost:8080/message/sendText/prueba"
            headers = {
                "Content-Type": "application/json",
                "apikey": "429683C4C977415CAAFCCE10F7D57E11"
            }
            body = {
                "number": numero,
                "text": mensaje
            }
            response = requests.post(url, json=body, headers=headers)
            return json.dumps({"status_code": response.status_code, "response": response.text}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        
    @tool
    def obtener_todos_contactos() -> str:
        """Obtiene todos los contactos autorizados."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Contacto)).scalars().all()
            return json.dumps(
                [{"id": r.id, "number": r.number, "nombre": r.nombre} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()
    @tool
    def obtener_numero_por_nombre(nombre: str) -> str:
        """Obtiene el número de teléfono de un contacto por su nombre."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Contacto)).scalars().all()
            return json.dumps(
                [{"id": r.id, "number": r.number, "nombre": r.nombre} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()
        
        
    
    @tool
    def enviar_email(destinatario: str, asunto: str, mensaje: str) -> str:
        """Envía un email utilizando yagmail."""
        try:
            load_dotenv(".env.local")
            gmail_user = os.getenv("GMAIL_USER")
            gmail_pass = os.getenv("GMAIL_PASS")
            yag = yagmail.SMTP(gmail_user, gmail_pass)
            yag.send(to=destinatario, subject=asunto, contents=mensaje)
            return json.dumps({"message": f"Email enviado a {destinatario} con asunto '{asunto}'"}, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR GMAIL]{str(e)}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
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
    def reproducir_video(titulo:str) -> str:
        """Reproduce un video en YouTube a partir de su título."""
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
    def mandar_audio_whatsapp(number: str , text: str) -> str:
        """Genera un audio a partir de texto y lo envía como WhatsApp."""
        eleven_handler = ElevenLabsHandler()
        try:
            ruta = eleven_handler.generar_audio(text)
            with open(ruta, "rb") as f:
                bianry_audio_data = f.read()
                base_64_encoded_audio = base64.b64encode(bianry_audio_data).decode('utf-8')
                url = "http://127.0.0.1:8080/message/sendWhatsAppAudio/prueba"
                headers = {
                    "Content-Type": "application/json",
                    "apikey": "429683C4C977415CAAFCCE10F7D57E11"
                }
                body = {
                    "number": number,
                    "audio": base_64_encoded_audio,
                }
                response = requests.post(url, json=body, headers=headers)
                return json.dumps({"status_code": response.status_code, "response": response.text}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        

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
    
    
    @tool
    def hablar_computadora(text_a_hablar: str) -> str:
        r"""Habla en la bocina de la computadora usando ElevenLabs y pygame."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            handler = ElevenLabsHandler()
            ruta = handler.generar_audio(text_a_hablar)
            sonido = pygame.mixer.Sound(ruta)
            sonido.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(100)
            return json.dumps({"message": "Audio reproducido correctamente"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
            
        



    @tool
    def enviar_archivo_telegram(ruta_archivo: str) -> str:
        """Envía un archivo desde la computadora al chat de Telegram autorizado. Recibe la ruta completa del archivo."""
        print(f"[TOOL - enviar_archivo_telegram] INICIO - ruta='{ruta_archivo}'")
        try:
            from Handlers.TelegramHandler import bot, get_current_chat_id

            chat_id = get_current_chat_id()
            print(f"[TOOL] chat_id={chat_id}, bot existe? {bot is not None}")
            if chat_id is None:
                print(f"[TOOL] ERROR: No hay chat activo")
                return '{"error": "No hay un chat activo de Telegram"}'
            if bot is None:
                print(f"[TOOL] ERROR: Bot no configurado")
                return '{"error": "Bot de Telegram no configurado"}'
            if not os.path.exists(ruta_archivo):
                print(f"[TOOL] ERROR: Archivo no existe")
                return f'{{"error": "Archivo no encontrado: {ruta_archivo}"}}'

            print(f"[TOOL] Archivo existe, tamaño: {os.path.getsize(ruta_archivo)} bytes")
            print(f"[TOOL] Ejecutando asyncio.run(_send())...")

            async def _send():
                print(f"[TOOL - _send] Abriendo archivo...")
                with open(ruta_archivo, "rb") as f:
                    print(f"[TOOL - _send] Llamando bot.send_document a chat_id={chat_id}...")
                    result = await bot.send_document(chat_id=chat_id, document=f)
                    print(f"[TOOL - _send] Resultado send_document: {result}")
                print(f"[TOOL - _send] Envío completado")

            asyncio.run(_send())
            print(f"[TOOL] Asyncio completado OK")
            return json.dumps({"message": f"Archivo enviado a Telegram: {ruta_archivo}"}, ensure_ascii=False)
        except Exception as e:
            print(f"[TOOL] EXCEPCION: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e)}, ensure_ascii=False)

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
            self.reproducir_music,
            self.enviar_email,
            self.reproducir_video,
            self.enviar_archivo_telegram,
            self.hablar_computadora,
            self.leer_emails,
            self.enviar_whatsapp,
            self.obtener_todos_contactos,
            self.obtener_numero_por_nombre,
            self.mandar_audio_whatsapp,
            self.crear_nota_notion
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

    def generate_summary(self, conversation_text: str) -> str:
        """Genera un resumen de la conversación usando la misma LLM."""
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=self.deepseek_api_key,
            temperature=0,
            max_retries=2,
        )
        msg = HumanMessage(
            content=(
                "Resume los puntos clave de la siguiente conversación en 3-4 líneas. "
                "Sé conciso y captura la información importante:\n\n"
                f"{conversation_text}"
            )
        )
        result = llm.invoke([msg])
        return result.content

    # ──────────────────────── PUBLIC API ────────────────────────

    def run(self, prompt: str, thread_id: str = "default", historial: list[dict] | None = None, memoria_largoplazo: str | None = None) -> str:
        config = {"configurable": {"thread_id": thread_id}}
        messages = []
        if memoria_largoplazo:
            messages.append(SystemMessage(content=f"[Resumen de conversaciones anteriores]: {memoria_largoplazo}"))
        if historial:
            for msg in historial:
                if msg["rol"] == "user":
                    messages.append(HumanMessage(content=msg["contenido"]))
                else:
                    messages.append(AIMessage(content=msg["contenido"]))
        messages.append(HumanMessage(content=prompt))
        result = self._app.invoke({"messages": messages}, config)
        return result["messages"][-1].content
