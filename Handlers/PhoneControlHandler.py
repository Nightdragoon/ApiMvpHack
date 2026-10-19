"""Canal de control para la app de telefono (uzi_apk).

La app Android necesita dos cosas que el canal de los esclavos (/ws-esclavo) no
da por si solo:

1. **Baja latencia**: el modo "control de Wii" manda decenas de `mouse_move_rel`
   por segundo. Hacer un POST HTTP por cada uno seria inviable, asi que el
   telefono abre un WebSocket (`/ws-control`) y manda los movimientos como
   fire-and-forget (sin esperar respuesta del esclavo).
2. **Hablar con Uzi**: por el mismo socket la app puede mandar texto (chat o
   dictado por voz) y recibir la respuesta de Uzi. Si la app tiene una PC
   seleccionada, se le agrega contexto al prompt para que Uzi actue sobre ESA
   PC (igual que hace el comando de voz del esclavo en SlaveServerHandler).

El telefono NUNCA habla directo con los esclavos: siempre pasa por aqui, y de
aqui se reusa SlaveServerHandler (que ya tiene el registro de PCs, la
numeracion y la correlacion de respuestas por id).

Protocolo (JSON de texto en los dos sentidos):

    servidor -> telefono, al conectar:
        {"type": "hello_ok", "pcs": [...]}

    telefono -> servidor:
        {"type": "pcs"}                                   # pedir la lista
        {"type": "input", "pc": 1, "action": "mouse_move_rel",
         "params": {"dx": 4, "dy": -2}}                   # sin respuesta
        {"type": "cmd", "id": "c1", "pc": 1, "action": "screenshot",
         "params": {}, "timeout": 30}                     # con respuesta
        {"type": "chat", "id": "m1", "text": "pon musica", "pc": 1}
        {"type": "ping"}

    servidor -> telefono:
        {"type": "pcs", "pcs": [...]}
        {"type": "result", "id": "c1", "status": "ok", "result": {...}}
        {"type": "chat_reply", "id": "m1", "status": "ok", "text": "..."}
        {"type": "error", "id": "...", "message": "..."}
        {"type": "pong"}
"""

import asyncio
import json
import os
from typing import Optional, TYPE_CHECKING

from Handlers.SlaveServerHandler import get_slave_server

if TYPE_CHECKING:
    from fastapi import WebSocket

def _token_esperado() -> str:
    """Token opcional para que no cualquiera abra el canal de control. Si esta
    vacio el canal queda abierto (igual que AGENT_TOKEN en los esclavos).

    Se lee en cada conexion y no al importar, porque main.py carga el
    .env.local despues de los imports.
    """
    return os.getenv("PHONE_TOKEN", "")

# Acciones que el telefono puede disparar. El control remoto es potente (mueve
# el mouse, escribe, abre apps), pero NO le abrimos la shell ni Claude Code:
# para eso el usuario le pide a Uzi por chat, que es donde hay un modelo
# decidiendo en medio.
ACCIONES_PERMITIDAS = {
    "ping",
    "info",
    "mouse_move",
    "mouse_move_rel",
    "mouse_position",
    "mouse_click",
    "mouse_down",
    "mouse_up",
    "scroll",
    "type_text",
    "press_key",
    "press_keys",
    "media",
    "window",
    "screenshot",
    "open_url",
    "open_youtube",
    "open_youtube_music",
    "open_app",
    "list_files",
}

# Acciones de control continuo: se mandan sin esperar respuesta para que el
# control se sienta en tiempo real.
ACCIONES_FIRE_AND_FORGET = {
    "mouse_move_rel",
    "mouse_move",
    "scroll",
    "mouse_click",
    "mouse_down",
    "mouse_up",
}


def prompt_con_contexto_pc(texto: str, numero_pc: Optional[int]) -> str:
    """Envuelve el mensaje del usuario con contexto de la PC seleccionada.

    En el modo "general" (sin PC) el texto se manda tal cual. Si la app tiene
    una PC seleccionada, se le dice a Uzi que ahi es donde debe actuar si la
    orden no especifica otra, igual que con los comandos de voz.
    """
    texto = (texto or "").strip()
    if numero_pc is None:
        return texto

    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)
    info = server.agent_info.get(agent_id or "", {})
    hostname = info.get("hostname", "?")
    return (
        f"[Mensaje desde la app del telefono. El usuario tiene seleccionada la "
        f"PC {numero_pc} ({hostname}). Si la orden no dice en que PC hacerlo, "
        f"hazlo en la PC {numero_pc}. Responde corto, se va a leer en voz alta "
        f"en el telefono.]\n{texto}"
    )


def thread_id_de(numero_pc: Optional[int], thread_id: Optional[str]) -> str:
    """Hilo de conversacion: uno por PC y uno para el modo general."""
    if thread_id:
        return thread_id
    if numero_pc is None:
        return "telefono-general"
    return f"telefono-pc{numero_pc}"


def _uzi():
    """Instancia compartida de Uzi (reusa la del servidor de esclavos para no
    perder el historial de cada hilo)."""
    return get_slave_server()._get_uzi()


async def preguntar_a_uzi(texto: str, numero_pc: Optional[int] = None,
                          thread_id: Optional[str] = None) -> str:
    """Corre un mensaje en Uzi (en un hilo aparte) y devuelve su respuesta."""
    prompt = prompt_con_contexto_pc(texto, numero_pc)
    if not prompt:
        return "No me llego ningun mensaje."
    hilo = thread_id_de(numero_pc, thread_id)
    handler = _uzi()
    return await asyncio.to_thread(handler.run, prompt, hilo)


async def ejecutar_en_pc(numero_pc: int, accion: str, params: Optional[dict] = None,
                         esperar: bool = True, timeout: float = 30) -> dict:
    """Manda una accion a una PC esclava desde el telefono.

    Devuelve un dict con `status` ("ok"/"error") y `result`. Con
    `esperar=False` no se espera la respuesta del esclavo (modo control).
    """
    if accion not in ACCIONES_PERMITIDAS:
        return {"status": "error", "result": f"Accion no permitida desde el telefono: {accion}"}

    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)
    if not agent_id:
        return {"status": "error", "result": f"La PC {numero_pc} no existe o nunca se ha conectado."}
    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        return {"status": "error",
                "result": f"La PC {numero_pc} ({info.get('hostname', '?')}) esta desconectada."}

    if not esperar:
        ok = await server.send_command_fire_and_forget(agent_id, accion, params or {})
        return {"status": "ok" if ok else "error",
                "result": {"enviado": accion} if ok else "No se pudo enviar el comando."}

    try:
        return await server.send_command(agent_id, accion, params or {}, timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "error", "result": f"La PC {numero_pc} no respondio en {timeout}s."}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "result": str(e)}


class PhoneControlHandler:
    """Maneja las conexiones WebSocket de las apps de telefono."""

    def __init__(self):
        self.phones: list["WebSocket"] = []

    # ----------------------------------------------------------------- #
    # Ciclo de vida
    # ----------------------------------------------------------------- #
    async def handle(self, ws: "WebSocket", token: str = ""):
        esperado = _token_esperado()
        if esperado and token != esperado:
            await ws.close(code=1008, reason="token invalido")
            return

        await ws.accept()
        self.phones.append(ws)
        server = get_slave_server()
        # El telefono puede ser la primera conexion del proceso; sin esto las
        # tools de Uzi no sabrian en que loop mandar los comandos.
        if server.loop is None:
            server.loop = asyncio.get_running_loop()

        print(f"[FONO] Telefono conectado ({len(self.phones)} activos)")
        try:
            await self._enviar(ws, {"type": "hello_ok", "pcs": server.get_pcs()})
            async for raw in ws.iter_text():
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._enviar(ws, {"type": "error", "message": "JSON invalido"})
                    continue
                # Cada mensaje se procesa en su propia task: un chat con Uzi
                # tarda segundos y no debe frenar los movimientos del mouse.
                asyncio.create_task(self._procesar(ws, msg))
        except Exception as e:  # noqa: BLE001
            print(f"[FONO] Conexion terminada: {type(e).__name__}: {e}")
        finally:
            if ws in self.phones:
                self.phones.remove(ws)
            print(f"[FONO] Telefono desconectado ({len(self.phones)} activos)")

    async def _enviar(self, ws: "WebSocket", payload: dict):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:  # noqa: BLE001
            print(f"[FONO] Error enviando al telefono: {e}")

    # ----------------------------------------------------------------- #
    # Mensajes
    # ----------------------------------------------------------------- #
    async def _procesar(self, ws: "WebSocket", msg: dict):
        tipo = msg.get("type")
        msg_id = msg.get("id")

        if tipo == "ping":
            await self._enviar(ws, {"type": "pong"})
            return

        if tipo == "pcs":
            await self._enviar(ws, {"type": "pcs", "pcs": get_slave_server().get_pcs()})
            return

        if tipo in ("input", "cmd"):
            numero_pc = msg.get("pc")
            accion = msg.get("action")
            if numero_pc is None or not accion:
                await self._enviar(ws, {"type": "error", "id": msg_id,
                                        "message": "Faltan 'pc' o 'action'"})
                return
            # 'input' nunca espera; 'cmd' espera salvo que sea una accion de
            # control continuo donde la respuesta no aporta nada.
            esperar = tipo == "cmd" and accion not in ACCIONES_FIRE_AND_FORGET
            resultado = await ejecutar_en_pc(
                int(numero_pc), accion, msg.get("params") or {},
                esperar=esperar, timeout=float(msg.get("timeout", 30)),
            )
            if tipo == "cmd":
                await self._enviar(ws, {"type": "result", "id": msg_id,
                                        "status": resultado.get("status"),
                                        "result": resultado.get("result")})
            elif resultado.get("status") == "error":
                # En modo control solo avisamos cuando algo falla (p.ej. la PC
                # se desconecto a media sesion).
                await self._enviar(ws, {"type": "error", "id": msg_id,
                                        "message": str(resultado.get("result"))})
            return

        if tipo == "chat":
            texto = msg.get("text") or ""
            numero_pc = msg.get("pc")
            try:
                respuesta = await preguntar_a_uzi(
                    texto,
                    int(numero_pc) if numero_pc is not None else None,
                    msg.get("thread_id"),
                )
                await self._enviar(ws, {"type": "chat_reply", "id": msg_id,
                                        "status": "ok", "text": respuesta})
            except Exception as e:  # noqa: BLE001
                print(f"[FONO] Error en chat con Uzi: {e}")
                await self._enviar(ws, {"type": "chat_reply", "id": msg_id,
                                        "status": "error",
                                        "text": f"Hubo un error hablando con Uzi: {e}"})
            return

        await self._enviar(ws, {"type": "error", "id": msg_id,
                                "message": f"Tipo de mensaje desconocido: {tipo}"})


phone_control_global: Optional[PhoneControlHandler] = None


def get_phone_control() -> PhoneControlHandler:
    global phone_control_global
    if phone_control_global is None:
        phone_control_global = PhoneControlHandler()
    return phone_control_global
