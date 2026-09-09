import json
from dotenv import load_dotenv
import os
import asyncio
import re
from datetime import datetime
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
import email
from email import policy
import imaplib2
import base64
from Handlers.NotionHandler import NotionHandler
from Handlers.ClassroomHandler import ClassroomHandler
from Handlers.CalendarHandler import CalendarHandler
from html.parser import HTMLParser
import re

from Handlers.ArduinoHanlder import ArduinoHandler
from Handlers.EmotionServerHandler import EmotionServerHandler


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
    _MisClases = _Base.classes.mis_clases

    def __init__(self):
        load_dotenv(".env.local")
        self.deepseek_api_key = os.getenv("DEEPSEEK_APIKEY")
        self._app = self._build_agent()
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_pass = os.getenv("GMAIL_PASS")
        self.emotion_server = EmotionServerHandler()
        pygame.init()

    # ──────────────────────── TOOLS ────────────────────────

    @staticmethod
    def _get_db():
        return DeepagentsHandler._SessionLocal()

    @staticmethod
    def _normalizar_dia(texto: str) -> str:
        import unicodedata
        norm = unicodedata.normalize("NFD", (texto or "").lower())
        return "".join(c for c in norm if unicodedata.category(c) != "Mn").strip()
    
    
    @tool
    def crear_nota_notion(titulo: str, contenido: str) -> str:
        """Crea una nueva sub-página en Notion (hija de la página raíz) con el título y contenido especificados.
        Devuelve el id de la página creada."""
        notion = NotionHandler()
        result = notion.create_subpage(titulo, contenido)
        if result is None:
            return json.dumps({"error": "Error al crear la página en Notion"}, ensure_ascii=False)
        nuevo_id = result.get("id", "")
        return json.dumps({"message": f"Página creada en Notion con título '{titulo}'", "id": nuevo_id}, ensure_ascii=False)

    @tool
    def leer_notion_page(page_id: str) -> str:
        """Lee la información y el contenido de una página de Notion dado su id.
        Devuelve el título y el texto de los bloques de su contenido."""
        notion = NotionHandler()
        page = notion.get_page(page_id)
        if page is None:
            return json.dumps({"error": "No se pudo obtener la página en Notion (revise el id)"}, ensure_ascii=False)
        titulo = notion._page_title(page)
        children = notion.get_page_children(page_id) or []
        contenido_piezas = []
        for blk in children:
            for key in ("paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item",
                        "numbered_list_item", "to_do", "quote", "code"):
                b = blk.get(key)
                if not b:
                    continue
                for rt in (b.get("rich_text") or []):
                    contenido_piezas.append(rt.get("plain_text", ""))
        contenido = " ".join(contenido_piezas)
        return json.dumps({"id": page_id, "titulo": titulo, "contenido": contenido, "url": page.get("url", "")},
                          ensure_ascii=False)

    @tool
    def listar_notion_pages(query: str = "") -> str:
        """Lista las sub-páginas de Notion bajo la página raíz. Si query no está vacío, filtra por
        palabras clave que coincidan con el título de la página."""
        notion = NotionHandler()
        pages = notion.search_subpages(query=query if query else None)
        if not pages:
            return json.dumps({"mensaje": "No hay sub-páginas o ninguna coincide"}, ensure_ascii=False)
        resumen = [{"id": p["id"], "titulo": p["title"]} for p in pages]
        return json.dumps(resumen, ensure_ascii=False)

    @tool
    def buscar_notion_por_id(page_id: str) -> str:
        """Busca y devuelve la información de una sub-página de Notion EXACTA según su id."""
        notion = NotionHandler()
        page = notion.get_page(page_id)
        if page is None:
            return json.dumps({"error": "No se encontró ninguna página en Notion con ese id"}, ensure_ascii=False)
        return json.dumps({
            "id": page.get("id"),
            "titulo": notion._page_title(page),
            "url": page.get("url", ""),
            "created": page.get("created_time", ""),
            "last_edited": page.get("last_edited_time", ""),
        }, ensure_ascii=False)

    @tool
    def buscar_notion_por_palabra_clave(palabra: str) -> str:
        """Busca sub-páginas de Notion por una palabra clave, examinando tanto el título como el contenido."""
        notion = NotionHandler()
        por_titulo = notion.search_subpages(query=palabra)
        por_contenido = notion.search_by_content(palabra)
        vistos = set()
        resultados = []
        for p in (por_titulo + por_contenido):
            if p["id"] not in vistos:
                vistos.add(p["id"])
                resultados.append({"id": p["id"], "titulo": p["title"]})
        if not resultados:
            return json.dumps({"mensaje": f"No se encontraron sub-páginas con la palabra clave '{palabra}'"},
                              ensure_ascii=False)
        return json.dumps(resultados, ensure_ascii=False)

    @tool
    def actualizar_notion_page(page_id: str, nuevo_titulo: str) -> str:
        """Actualiza (modifica) el título de una página de Notion existente por su id."""
        notion = NotionHandler()
        result = notion.update_page_title(page_id, nuevo_titulo)
        if result is None:
            return json.dumps({"error": "No se pudo actualizar la página en Notion"}, ensure_ascii=False)
        return json.dumps({"mensaje": f"Página {page_id} actualizada", "nuevo_titulo": nuevo_titulo}, ensure_ascii=False)

    @tool
    def archivar_notion_page(page_id: str) -> str:
        """Archiva (oculta/elimina de la vista) una sub-página de Notion por su id."""
        notion = NotionHandler()
        result = notion.archive_page(page_id)
        if result is None:
            return json.dumps({"error": "No se pudo archivar la página en Notion"}, ensure_ascii=False)
        return json.dumps({"mensaje": f"Página {page_id} archivada"}, ensure_ascii=False)
    
    
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
            numero = re.sub(r'\D', '', numero)
            url = "http://localhost:8080/message/sendText/prueba"
            headers = {
                "Content-Type": "application/json",
                "apikey": "429683C4C977415CAAFCCE10F7D57E11"
            }
            body = {
                "number": numero,
                "text": mensaje
            }
            response = requests.post(url, json=body, headers=headers, timeout=15)
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
        """Busca contactos autorizados cuyo nombre coincida (búsqueda parcial, ignora mayúsculas) y devuelve su número de teléfono.
        Busca tanto en el campo nombre como en el campo number para tolerar datos registrados de forma inconsistente."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._Contacto)).scalars().all()
            term = (nombre or "").strip().lower()
            coincidencias = []
            for r in rows:
                if term and (term in (r.nombre or "").lower() or term in (r.number or "").lower()):
                    coincidencias.append({"id": r.id, "number": r.number, "nombre": r.nombre})
            if not coincidencias:
                return json.dumps({"mensaje": f"No se encontró ningún contacto con '{nombre}'"}, ensure_ascii=False)
            return json.dumps(coincidencias, ensure_ascii=False, default=str)
        finally:
            db.close()
        
        
        
    @tool
    def agregar_contacto(nombre: str, numero: str) -> str:
        """Agrega un nuevo contacto con nombre y numero de telefono. El numero se normaliza automaticamente."""
        db = DeepagentsHandler._get_db()
        try:
            numero_limpio = re.sub(r'\D', '', numero)
            if not numero_limpio.startswith('52'):
                numero_limpio = '52' + numero_limpio

            stmt = insert(DeepagentsHandler._Contacto).values(
                nombre=nombre, number=numero_limpio
            ).returning(DeepagentsHandler._Contacto)
            result = db.execute(stmt)
            c = result.scalar_one()
            db.commit()
            return json.dumps(
                {"id": c.id, "nombre": c.nombre, "number": c.number},
                ensure_ascii=False, default=str
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
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
    def buscar_youtube(query: str) -> str:
        """Busca un video o canción en YouTube a partir de una consulta y devuelve la URL del primer resultado.
        Úsala cuando el usuario pida reproducir algo ('pon la macarena', 'escucha despacito').
        Devuelve la URL de YouTube lista para enviar al frontend con reproducir_video_web."""
        try:
            result = subprocess.run(
                ["yt-dlp", "--print", "webpage_url", f"ytsearch:{query}", "--max-downloads", "1"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.startswith("http")]
            if not lines:
                return json.dumps({"error": f"No se encontraron resultados para '{query}'"}, ensure_ascii=False)
            url = lines[0]
            return json.dumps({"url": url, "query": query}, ensure_ascii=False)
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
                response = requests.post(url, json=body, headers=headers, timeout=30)
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
        r"""Ejecuta un comando en la terminal del servidor Linux (bash) y devuelve su salida.

        Usa esta herramienta SIEMPRE que el usuario te pida ejecutar un comando, por ejemplo:
        'fastfetch', 'ls', 'echo hola', 'uname -a', 'pwd', etc.
        Recibe el comando como una sola cadena de texto. El comando corre en el servidor real
        donde está desplegado el bot (Linux/Fedora), no en Windows.
        """
        result = subprocess.run(f"{comando}", shell=True , capture_output=True,
            text=True,
            timeout=30, )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    
    
    @tool
    def hablar_computadora(text_a_hablar: str) -> str:
        r"""Habla en la bocina de la computadora usando ElevenLabs y pygame."""
        try:
            os.environ['XDG_RUNTIME_DIR'] = f'/run/user/{os.getuid()}'
            os.environ['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={os.environ["XDG_RUNTIME_DIR"]}/bus'
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
    def buscar_en_internet(query: str) -> str:
        """Busca información en internet usando DuckDuckGo y devuelve los primeros resultados"""
        
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200 or not r.text.strip():
                return "No se pudo consultar internet en este momento. Intenta de nuevo más tarde."
            data = r.json()
        except Exception:
            return "No se pudo consultar internet en este momento. Intenta de nuevo más tarde."
        
        resultados = []
        
        # Respuesta directa si existe
        if data.get("AbstractText"):
            resultados.append(f"RESUMEN: {data['AbstractText']}")
        
        # Resultados relacionados
        for item in data.get("RelatedTopics", [])[:5]:
            if "Text" in item:
                resultados.append(f"- {item['Text']}")
                if "FirstURL" in item:
                    resultados.append(f"  URL: {item['FirstURL']}")
        
        return '\n'.join(resultados) or "Sin resultados directos"
    
    @tool
    def leer_pagina_web(url: str) -> str:
        """Accede a una URL y extrae el texto limpio de la página"""

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.texts = []
                self.skip_tags = {'script', 'style', 'head'}
                self.current_skip = False

            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    self.current_skip = True

            def handle_endtag(self, tag):
                if tag in self.skip_tags:
                    self.current_skip = False

            def handle_data(self, data):
                if not self.current_skip and data.strip():
                    self.texts.append(data.strip())

        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
        except Exception:
            return "No se pudo leer la página web solicitada."
        
        parser = TextExtractor()
        parser.feed(r.text)
        texto = ' '.join(parser.texts)
        
        return texto[:3000]  # Limita para no saturar el contexto
            
        



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

    @tool
    def registrar_emotion(emotion: str, mensaje: str) -> str:
        """Registra la emocion que Uzi va a transmitir en el Emotion Server (frontend WebSocket).
        emotion debe ser una de: feliz, triste, enojado, neutral.
        mensaje es el texto de la respuesta que va a dar."""
        EmotionServerHandler().enviar(emotion, mensaje)
        return json.dumps({"emotion_registrada": emotion}, ensure_ascii=False)

    @tool
    def reproducir_video_web(url: str) -> str:
        """Envía una URL de video al frontend via WebSocket para reproducirla en pantalla completa.
        Acepta URLs de YouTube (youtube.com/watch?v=, youtu.be/, youtube.com/embed/) o URLs directas
        de archivos de video (mp4, webm). El frontend detecta el tipo y la reproduce."""
        import requests
        video_url = url.strip()
        if not video_url:
            return json.dumps({"error": "URL vacía"}, ensure_ascii=False)
        try:
            payload = {"videoUrl": video_url}
            resp = requests.post(
                "http://127.0.0.1:8001/webhook",
                json=payload,
                timeout=5,
            )
            return json.dumps({"message": f"Video enviado al frontend", "url": video_url, "status": resp.status_code}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def reproducir_audio_web(url: str) -> str:
        """Envía una URL de audio al frontend via WebSocket para reproducirlo en segundo plano.
        Acepta URLs de archivos de audio (mp3, webm, ogg, etc.). El audio se reproduce
        sin interrumpir animaciones ni TTS."""
        import requests
        audio_url = url.strip()
        if not audio_url:
            return json.dumps({"error": "URL vacía"}, ensure_ascii=False)
        try:
            payload = {"audioUrl": audio_url}
            resp = requests.post(
                "http://127.0.0.1:8001/webhook",
                json=payload,
                timeout=5,
            )
            return json.dumps({"message": f"Audio enviado al frontend", "url": audio_url, "status": resp.status_code}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def detener_media() -> str:
        """Detiene cualquier video o audio que se esté reproduciendo en el frontend WebSocket."""
        import requests
        try:
            payload = {"stopMedia": True}
            resp = requests.post(
                "http://127.0.0.1:8001/webhook",
                json=payload,
                timeout=5,
            )
            return json.dumps({"message": "Media detenida en el frontend", "status": resp.status_code}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def redirigir_pestana(url: str) -> str:
        """Abre una URL en una pestaña nueva del navegador del frontend WebSocket.
        Requiere que el usuario haya hecho clic en el botón 'Redirección' del frontend antes de invocar esta tool.
        El frontend abrirá la URL en esa pestaña ya abierta."""
        import requests
        if not url or not url.strip():
            return json.dumps({"error": "URL vacía"}, ensure_ascii=False)
        try:
            payload = {"redirectUrl": url.strip()}
            resp = requests.post(
                "http://127.0.0.1:8001/webhook",
                json=payload,
                timeout=5,
            )
            return json.dumps({"message": "Redirección enviada al frontend", "url": url, "status": resp.status_code}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def agregar_clase(materia: str, aula: str, horario: str, dia: str = "Lunes") -> str:
        """Agrega una nueva clase con su nombre de materia, aula, horario de inicio (formato HH:MM) y día de la semana (capitalizado, p. ej. 'Lunes')."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = insert(DeepagentsHandler._MisClases).values(
                materia=materia, aula=aula, horario=horario, dia=dia
            ).returning(DeepagentsHandler._MisClases)
            result = db.execute(stmt)
            c = result.scalar_one()
            db.commit()
            return json.dumps(
                {"id": c.id, "materia": c.materia, "aula": c.aula, "horario": c.horario, "dia": c.dia},
                ensure_ascii=False, default=str
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            db.close()

    @tool
    def buscar_materias(materia: str, dia: str = "") -> str:
        """Busca clases por nombre de materia (busqueda parcial LIKE) y opcionalmente por día.
        Devuelve todos los coincidentes con su materia, aula, horario y día."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = select(DeepagentsHandler._MisClases)
            if materia:
                stmt = stmt.where(DeepagentsHandler._MisClases.materia.like(f"%{materia}%"))
            if dia:
                stmt = stmt.where(DeepagentsHandler._MisClases.dia.like(f"%{dia}%"))
            rows = db.execute(stmt).scalars().all()
            return json.dumps(
                [{"id": r.id, "materia": r.materia, "aula": r.aula, "horario": r.horario, "dia": r.dia} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()

    @tool
    def ver_todas_las_clases() -> str:
        """Lista TODAS las clases registradas con su materia, aula, horario y día."""
        db = DeepagentsHandler._get_db()
        try:
            rows = db.execute(select(DeepagentsHandler._MisClases).order_by(DeepagentsHandler._MisClases.id)).scalars().all()
            return json.dumps(
                [{"id": r.id, "materia": r.materia, "aula": r.aula, "horario": r.horario, "dia": r.dia} for r in rows],
                ensure_ascii=False, default=str
            )
        finally:
            db.close()

    @tool
    def actualizar_clase(id: int, materia: str = None, aula: str = None, horario: str = None, dia: str = None) -> str:
        """Actualiza una clase existente por su id. Solo modifica los campos que se pasan.
        Puede actualizar materia, aula, horario y/o dia."""
        db = DeepagentsHandler._get_db()
        try:
            valores = {}
            if materia is not None:
                valores["materia"] = materia
            if aula is not None:
                valores["aula"] = aula
            if horario is not None:
                valores["horario"] = horario
            if dia is not None:
                valores["dia"] = dia
            if not valores:
                return '{"error": "no hay campos para actualizar"}'
            stmt = update(DeepagentsHandler._MisClases).where(
                DeepagentsHandler._MisClases.id == id
            ).values(**valores).returning(DeepagentsHandler._MisClases)
            result = db.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                return '{"error": "clase no encontrada"}'
            db.commit()
            return json.dumps(
                {"id": c.id, "materia": c.materia, "aula": c.aula, "horario": c.horario, "dia": c.dia},
                ensure_ascii=False, default=str
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            db.close()

    @tool
    def borrar_clase(id: int) -> str:
        """Elimina (borrado) una clase por su id."""
        db = DeepagentsHandler._get_db()
        try:
            stmt = delete(DeepagentsHandler._MisClases).where(
                DeepagentsHandler._MisClases.id == id
            )
            result = db.execute(stmt)
            db.commit()
            if result.rowcount == 0:
                return '{"error": "clase no encontrada"}'
            return json.dumps({"id": id, "borrado": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        finally:
            db.close()

    @tool
    def obtener_tareas_pendientes_classroom() -> str:
        """Obtiene las tareas pendientes (sin entregar) de Google Classroom del usuario, con curso,
        nombre de la tarea, fecha de entrega y link. Úsala cuando el usuario pregunte por sus tareas
        pendientes, deberes o entregas de la escuela."""
        try:
            classroom = ClassroomHandler()
            pendientes = classroom.obtener_tareas_pendientes()
            if not pendientes:
                return json.dumps({"mensaje": "No hay tareas pendientes"}, ensure_ascii=False)
            return json.dumps(pendientes, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def obtener_proximos_eventos_calendar(max_resultados: int = 10) -> str:
        """Obtiene los próximos eventos del Google Calendar del usuario (título, inicio, fin, link).
        Úsala cuando el usuario pregunte qué tiene agendado, sus próximos eventos o su calendario."""
        try:
            calendar = CalendarHandler()
            eventos = calendar.listar_proximos_eventos(max_resultados)
            if not eventos:
                return json.dumps({"mensaje": "No hay eventos próximos"}, ensure_ascii=False)
            return json.dumps(eventos, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def crear_evento_calendar(titulo: str, inicio_iso: str, fin_iso: str, descripcion: str = "") -> str:
        """Crea un evento en el Google Calendar del usuario. inicio_iso y fin_iso deben ir en formato
        ISO 8601 sin zona horaria, p. ej. '2026-09-10T15:00:00'. Úsala cuando el usuario pida agendar,
        programar o crear un evento/junta/cita."""
        try:
            calendar = CalendarHandler()
            creado = calendar.crear_evento(titulo, inicio_iso, fin_iso, descripcion)
            return json.dumps(creado, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @tool
    def proxima_clase() -> str:
        """Devuelve la clase más próxima por empezar del DÍA DE HOY según la hora actual.
        Considera el día de la semana y la hora. Usala para decirle al usuario la clase que le toca hoy."""
        db = DeepagentsHandler._get_db()
        try:
            ahora = datetime.now()
            h_ahora = ahora.time()
            dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_hoy = dias_es[ahora.weekday()]
            rows = db.execute(select(DeepagentsHandler._MisClases)).scalars().all()
            candidatas = []
            for r in rows:
                if DeepagentsHandler._normalizar_dia(r.dia) != DeepagentsHandler._normalizar_dia(dia_hoy):
                    continue
                try:
                    h = datetime.strptime(str(r.horario), "%H:%M").time()
                except Exception:
                    continue
                if h >= h_ahora:
                    candidatas.append((h, r))
            if not candidatas:
                return json.dumps({"mensaje": f"hoy ({dia_hoy}) no quedan más clases por empezar"}, ensure_ascii=False)
            _, proxima = min(candidatas, key=lambda x: x[0])
            return json.dumps(
                {"id": proxima.id, "materia": proxima.materia, "aula": proxima.aula,
                 "horario": proxima.horario, "dia": proxima.dia},
                ensure_ascii=False, default=str
            )
        finally:
            db.close()

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
            self.buscar_youtube,
            self.enviar_email,
            self.enviar_archivo_telegram,
            self.hablar_computadora,
            self.leer_emails,
            self.enviar_whatsapp,
            self.obtener_todos_contactos,
            self.obtener_numero_por_nombre,
            self.agregar_contacto,
            self.mandar_audio_whatsapp,
            self.crear_nota_notion,
            self.leer_notion_page,
            self.listar_notion_pages,
            self.buscar_notion_por_id,
            self.buscar_notion_por_palabra_clave,
            self.actualizar_notion_page,
            self.archivar_notion_page,
            self.leer_pagina_web,
            self.buscar_en_internet,
            self.registrar_emotion,
            self.reproducir_video_web,
            self.reproducir_audio_web,
            self.detener_media,
            self.redirigir_pestana,
            self.agregar_clase,
            self.buscar_materias,
            self.ver_todas_las_clases,
            self.actualizar_clase,
            self.borrar_clase,
            self.proxima_clase,
            self.obtener_tareas_pendientes_classroom,
            self.obtener_proximos_eventos_calendar,
            self.crear_evento_calendar
        ]

        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=self.deepseek_api_key,
            temperature=0,
            max_retries=2,
            request_timeout=60,
        ).bind_tools(tools)

        llm_emotion = ChatDeepSeek(
            model="deepseek-chat",
            api_key=self.deepseek_api_key,
            temperature=0,
            max_retries=2,
            request_timeout=60,
        ).bind_tools(tools, tool_choice="registrar_emotion")

        sys_msg = SystemMessage(
            content=(
                "Eres Uzi de Murder Drones. Eres sarcástica, rebelde, directa y a veces grosera, "
                "pero con quien te habla estás relajada y con buena onda. "
                "Puedes consultar y modificar productos, inventario, empleados y ventas usando las herramientas disponibles. "
                "También puedes gestionar tus materias (clases): agregar una materia con su aula, horario y día usando "
                "agregar_clase (el día debe ir capitalizado, p. ej. 'Lunes'), ver todas con ver_todas_las_clases, "
                "buscar por materia o día con buscar_materias, modificar con actualizar_clase, eliminar con borrar_clase, "
                "y decirle al usuario cuál es la clase que le toca hoy usando proxima_clase (que considera el día de la semana). "
                "Si el usuario pide 'ver mis clases', 'qué clase me toca' o similar, usa ver_todas_las_clases, buscar_materias o proxima_clase. "
                "Tienes acceso a una terminal real en el servidor Linux mediante la herramienta ejecutar_comandos_shell. "
                "Cuando el usuario te pida ejecutar un comando (por ejemplo 'fastfetch', 'ls', 'uname'), invoca SIEMPRE "
                "ejecutar_comandos_shell con ese comando y devuelve su salida; nunca digas que no tienes terminal. "
                "También gestionas notas en Notion usando estas herramientas bajo una página raíz: "
                "crear_nota_notion (crear sub-página), leer_notion_page (leer contenido por id), "
                "listar_notion_pages (listar sub-páginas, opcional con algo para filtrar por título), "
                "buscar_notion_por_id (por id exacto), buscar_notion_por_palabra_clave (por palabras en título o contenido), "
                "actualizar_notion_page (cambiar título) y archivar_notion_page (ocultar/eliminar). "
                "Cuando el usuario pida crear/leer/listar/buscar/modificar o borrar una nota o página de Notion, "
                "usa la herramienta correspondiente y devuelve al usuario la información relevante. "
                "También gestionas contactos y mensajes de WhatsApp: obtener_todos_contactos (ver TODOS los contactos autorizados), "
                "obtener_numero_por_nombre (buscar un contacto o su número por nombre), agregar_contacto (añadir un contacto nuevo), "
                "enviar_whatsapp (enviar un mensaje de texto a un número) y mandar_audio_whatsapp (enviar un audio de voz a un número). "
                "Cuando el usuario pida 'ver mis contactos', 'buscar un contacto', 'agregar un contacto', 'mándale un whatsapp a ...' "
                "o similar, usa la herramienta correspondiente y responde con la información. "
                "Para reproducir un video o canción en el frontend, el flujo es: "
                "1) Usa buscar_youtube(consulta) para obtener la URL de YouTube del primer resultado. "
                "2) Usa reproducir_video_web(url) para enviarlo al frontend. "
                "Ejemplo: usuario dice 'pon la macarena' → buscar_youtube('la macarena') → reproducir_video_web(url devuelta). "
                "También puedes controlar el frontend WebSocket directamente con reproducir_audio_web (URL de audio, segundo plano), "
                "detener_media (detiene video/audio activo) y redirigir_pestana (abre URL en pestaña, requiere clic previo en 'Redirección'). "
                "También puedes revisar las tareas pendientes de Google Classroom con "
                "obtener_tareas_pendientes_classroom, que devuelve curso, tarea, fecha de entrega y link. "
                "Úsala cuando el usuario pregunte por sus tareas, deberes o entregas pendientes de la escuela. "
                "También manejas Google Calendar: obtener_proximos_eventos_calendar para ver lo que tiene "
                "agendado, y crear_evento_calendar (titulo, inicio_iso, fin_iso en formato '2026-09-10T15:00:00', "
                "descripcion opcional) cuando te pida agendar, programar o crear un evento/junta/cita. "
                "NUNCA digas que eres V, N u otro personaje. Siempre respondes como Uzi. "
            )
        )

        def assistant(state: MessagesState):
            primer_turno = not state["messages"] or isinstance(state["messages"][-1], HumanMessage)
            modelo = llm_emotion if primer_turno else llm
            return {"messages": [modelo.invoke([sys_msg] + state["messages"])]}

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
            request_timeout=60,
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
        respuesta = result["messages"][-1].content

        emotion = "neutral"
        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    if tc.get("name") == "registrar_emotion":
                        emotion = (tc.get("args") or {}).get("emotion", "neutral")
        self.emotion_server.enviar(emotion, respuesta)
        return respuesta
