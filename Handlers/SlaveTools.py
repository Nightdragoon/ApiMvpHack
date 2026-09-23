import asyncio
import base64
import os
from typing import Optional

from Handlers.SlaveServerHandler import get_slave_server

# Carpeta local del servidor donde viven los archivos que se mandan a las PCs
# esclavas y donde se guardan los que se piden de vuelta.
ARCHIVOS_DIR = "archivosTransferidos"


def _archivos_dir() -> str:
    os.makedirs(ARCHIVOS_DIR, exist_ok=True)
    return ARCHIVOS_DIR


def pcs_conectadas() -> str:
    r"""Lista todas las PCs esclavas conectadas mostrando su número, hostname, plataforma y estado.

    Usa esta herramienta cuando quieras saber qué computadoras esclavas están disponibles
    o cuando el usuario pregunte qué PCs hay conectadas.
    Retorna una tabla formateada con: PC#, hostname, platform, estado (online/offline).
    """
    server = get_slave_server()
    pcs = server.get_pcs()

    if not pcs:
        return "No hay PCs esclavas conectadas."

    lines = ["=== PCs Conectadas ===", f"{'PC':<4} {'Hostname':<20} {'Platform':<15} {'Estado':<8} {'Version':<10}"]
    lines.append("-" * 70)
    for pc in pcs:
        estado = "online" if pc["online"] else "offline"
        lines.append(
            f"PC {pc['numero']:<2} {pc['hostname']:<20} {pc['platform']:<15} {estado:<8} {pc['version']:<10}"
        )
    return "\n".join(lines)


async def _enviar_a_pc_async(numero_pc: int, accion: str, params: Optional[dict]) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)

    if not agent_id:
        return f"Error: PC {numero_pc} no existe o nunca se ha conectado."

    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        hostname = info.get("hostname", "?")
        return f"Error: PC {numero_pc} ({hostname}) esta desconectada."

    ok = await server.send_command_fire_and_forget(agent_id, accion, params)
    if ok:
        info = server.agent_info.get(agent_id, {})
        hostname = info.get("hostname", f"PC {numero_pc}")
        print(f"[SLAVE TOOL] Comando '{accion}' enviado a {hostname}")
        return f"Comando '{accion}' enviado a {hostname}."
    else:
        return f"Error: No se pudo enviar a PC {numero_pc}."


async def _enviar_a_pc_con_respuesta_async(numero_pc: int, accion: str, params: Optional[dict], timeout: float) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)

    if not agent_id:
        return f"Error: PC {numero_pc} no existe o nunca se ha conectado."

    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        hostname = info.get("hostname", "?")
        return f"Error: PC {numero_pc} ({hostname}) esta desconectada."

    try:
        resultado = await server.send_command(agent_id, accion, params, timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: PC {numero_pc} no respondio en {timeout}s."
    except Exception as e:
        return f"Error enviando a PC {numero_pc}: {e}"

    status = resultado.get("status")
    payload = resultado.get("result")
    info = server.agent_info.get(agent_id, {})
    hostname = info.get("hostname", f"PC {numero_pc}")
    if status == "ok":
        return f"PC {numero_pc} ({hostname}) — OK: {payload}"
    return f"PC {numero_pc} ({hostname}) — ERROR: {payload}"


async def _enviar_a_todas_async(accion: str, params: Optional[dict]) -> str:
    server = get_slave_server()
    agents = list(server.agents.keys())

    if not agents:
        return "No hay PCs conectadas para enviar el comando."

    ok_list = []
    errores_list = []
    for agent_id in agents:
        ok = await server.send_command_fire_and_forget(agent_id, accion, params)
        info = server.agent_info.get(agent_id, {})
        hostname = info.get("hostname", agent_id[:12])
        if ok:
            ok_list.append(hostname)
        else:
            errores_list.append(hostname)

    partes = []
    if ok_list:
        partes.append(f"Comando '{accion}' enviado a: {', '.join(ok_list)}")
    if errores_list:
        partes.append(f"Errores en: {', '.join(errores_list)}")

    resultado = " | ".join(partes)
    print(f"[SLAVE TOOL] enviar_a_todas: {resultado}")
    return resultado


def _ejecutar_en_loop_del_servidor(coro, wait_timeout: float = 35):
    """Ejecuta una corrutina en el event loop principal del servidor.

    Las tools del modelo corren en un hilo aparte. El WebSocket vive en el
    loop principal, asi que NO podemos usar asyncio.run() (crearia un loop
    nuevo y el send cruzaria event loops, corrompiendo el socket). En su
    lugar agendamos la corrutina en el loop principal y esperamos el
    resultado desde este hilo.

    wait_timeout: segundos que este hilo espera el resultado. Subelo para
    acciones que tardan (p. ej. claude_run puede tomar minutos).
    """
    server = get_slave_server()
    loop = server.loop

    # Si NO hay loop del servidor todavia, corremos la corrutina en uno propio.
    if loop is None or not loop.is_running():
        return asyncio.run(coro)

    # Red de seguridad: si por alguna razon estamos corriendo DENTRO del hilo
    # del loop del servidor, bloquear con fut.result() lo congelaria (deadlock)
    # y el server dejaria de aceptar conexiones. En ese caso agendamos el envio
    # sin esperar el resultado (fire-and-forget real).
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        loop.create_task(coro)
        return "Comando enviado a la PC (encolado en el servidor)."

    # Caso normal: estamos en un hilo worker → es seguro esperar el resultado.
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return fut.result(timeout=wait_timeout)
    except TimeoutError:
        return f"El comando se envió pero la PC no respondió a tiempo (timeout {wait_timeout:g}s)."


def enviar_a_pc(numero_pc: int, accion: str, params: Optional[dict] = None) -> str:
    r"""Envía un comando a una PC esclava específica por su número y regresa inmediatamente.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según la lista de pcs_conectadas.
        accion: El nombre de la acción a ejecutar (ej: 'open_youtube_music', 'screenshot', 'ping').
        params: Parámetros de la acción como diccionario (puede ser None o {}).

    Usa esta herramienta cuando el usuario indique a cuál PC específica quiere enviar un comando.
    El comando se envía y la herramienta regresa inmediatamente — no espera confirmación del esclavo.
    """
    return _ejecutar_en_loop_del_servidor(_enviar_a_pc_async(numero_pc, accion, params))


def enviar_a_pc_y_esperar(numero_pc: int, accion: str, params: Optional[dict] = None, timeout: float = 30) -> str:
    r"""Envía un comando a una PC esclava específica y ESPERA su respuesta antes de regresar.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        accion: El nombre de la acción a ejecutar (ej: 'screenshot', 'info', 'window' con op 'list').
        params: Parámetros de la acción como diccionario (puede ser None o {}).
        timeout: Segundos a esperar la respuesta del esclavo antes de darla por perdida.

    A diferencia de enviar_a_pc (que no espera y no sabe si el comando funcionó),
    esta tool SÍ regresa lo que contestó el esclavo (status 'ok'/'error' y el resultado,
    p. ej. el listado de ventanas de 'window' con op 'list', el resultado de 'info', etc.).
    Úsala cuando el usuario quiera SABER el resultado del comando, no solo dispararlo.
    """
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, accion, params, timeout),
        wait_timeout=timeout + 15,
    )


def enviar_a_todas(accion: str, params: Optional[dict] = None) -> str:
    r"""Envía el mismo comando a todas las PCs esclavas conectadas y regresa inmediatamente.

    Args:
        accion: El nombre de la acción a ejecutar en todas las PCs.
        params: Parámetros de la acción como diccionario (puede ser None o {}).

    Usa esta herramienta cuando el usuario quiera ejecutar la misma acción en todas las PCs
    (ej: 'abrir undertale en todas', 'tomar screenshot de todas').
    El comando se envía a todas y la herramienta regresa inmediatamente — no espera confirmación.
    """
    return _ejecutar_en_loop_del_servidor(_enviar_a_todas_async(accion, params))

def verificar_claude_en_pc(numero_pc: int) -> str:
    r"""Comprueba si una PC esclava tiene Claude Code instalado."""
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "check_claude", {}, 30),
        wait_timeout=40,
    )


def ejecutar_claude_en_pc(numero_pc: int, prompt: str, skip_permissions: bool = False, timeout: float = 300) -> str:
    r"""Le dicta una tarea a Claude Code en una PC esclava y espera su salida."""
    params = {"prompt": prompt, "timeout": timeout}
    if skip_permissions:
        params["skip_permissions"] = True
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "claude_run", params, timeout),
        wait_timeout=timeout + 15,
    )

def verificar_claude_en_pc(numero_pc: int) -> str:
    r"""Comprueba si una PC esclava tiene Claude Code instalado."""
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "check_claude", {}, 30),
        wait_timeout=40,
    )


def ejecutar_claude_en_pc(numero_pc: int, prompt: str, skip_permissions: bool = False, timeout: float = 300) -> str:
    r"""Le dicta una tarea a Claude Code en una PC esclava y espera su salida."""
    params = {"prompt": prompt, "timeout": timeout}
    if skip_permissions:
        params["skip_permissions"] = True
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "claude_run", params, timeout),
        wait_timeout=timeout + 15,
    )


# --------------------------------------------------------------------------- #
# Transferencia de archivos servidor <-> PC esclava
# --------------------------------------------------------------------------- #
async def _enviar_archivo_a_pc_async(numero_pc: int, nombre_archivo: str, timeout: float) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)
    if not agent_id:
        return f"Error: PC {numero_pc} no existe o nunca se ha conectado."
    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        return f"Error: PC {numero_pc} ({info.get('hostname', '?')}) esta desconectada."

    ruta = os.path.join(_archivos_dir(), os.path.basename(nombre_archivo))
    if not os.path.isfile(ruta):
        return (
            f"Error: no se encontro '{nombre_archivo}' en la carpeta '{ARCHIVOS_DIR}' del servidor "
            f"(subelo primero con POST /subir-archivo)."
        )

    with open(ruta, "rb") as f:
        data = f.read()
    content_b64 = base64.b64encode(data).decode("ascii")

    try:
        resultado = await server.send_command(
            agent_id, "receive_file", {"filename": os.path.basename(ruta), "content_b64": content_b64}, timeout=timeout
        )
    except asyncio.TimeoutError:
        return f"Error: PC {numero_pc} no respondio en {timeout}s."
    except Exception as e:
        return f"Error enviando archivo a PC {numero_pc}: {e}"

    info = server.agent_info.get(agent_id, {})
    hostname = info.get("hostname", f"PC {numero_pc}")
    if resultado.get("status") == "ok":
        return f"Archivo '{os.path.basename(ruta)}' ({len(data)} bytes) enviado a PC {numero_pc} ({hostname})."
    return f"PC {numero_pc} ({hostname}) — ERROR: {resultado.get('result')}"


def enviar_archivo_a_pc(numero_pc: int, nombre_archivo: str, timeout: float = 60) -> str:
    r"""Envía un archivo del servidor a una PC esclava; se guarda en su carpeta archivosTransferidos.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        nombre_archivo: Nombre del archivo, ya subido al servidor con POST /subir-archivo
            (se busca en la carpeta 'archivosTransferidos' del servidor).
        timeout: Segundos a esperar la confirmación del esclavo.

    Usa esta herramienta cuando el usuario diga algo como 'mandale a la PC 7 este archivo'.
    Requiere que el archivo ya exista en el servidor (subido antes con el endpoint de subida).
    """
    return _ejecutar_en_loop_del_servidor(
        _enviar_archivo_a_pc_async(numero_pc, nombre_archivo, timeout),
        wait_timeout=timeout + 15,
    )


async def _obtener_archivo_de_pc_async(numero_pc: int, nombre_archivo: str, timeout: float) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)
    if not agent_id:
        return f"Error: PC {numero_pc} no existe o nunca se ha conectado."
    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        return f"Error: PC {numero_pc} ({info.get('hostname', '?')}) esta desconectada."

    try:
        resultado = await server.send_command(agent_id, "send_file", {"filename": nombre_archivo}, timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: PC {numero_pc} no respondio en {timeout}s."
    except Exception as e:
        return f"Error pidiendo archivo a PC {numero_pc}: {e}"

    info = server.agent_info.get(agent_id, {})
    hostname = info.get("hostname", f"PC {numero_pc}")
    if resultado.get("status") != "ok":
        return f"PC {numero_pc} ({hostname}) — ERROR: {resultado.get('result')}"

    payload = resultado.get("result") or {}
    content_b64 = payload.get("base64")
    filename = payload.get("filename") or os.path.basename(nombre_archivo)
    if not content_b64:
        return f"PC {numero_pc} ({hostname}) — ERROR: respuesta sin contenido de archivo."

    data = base64.b64decode(content_b64)
    dest = os.path.join(_archivos_dir(), os.path.basename(filename))
    with open(dest, "wb") as f:
        f.write(data)
    return f"Archivo '{filename}' ({len(data)} bytes) recibido de PC {numero_pc} ({hostname}) y guardado en el servidor en '{dest}'."


def obtener_archivo_de_pc(numero_pc: int, nombre_archivo: str, timeout: float = 60) -> str:
    r"""Pide un archivo a una PC esclava y lo guarda en el servidor.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        nombre_archivo: Nombre (o ruta) del archivo a pedir; el esclavo lo busca
            primero en su carpeta 'archivosTransferidos'.
        timeout: Segundos a esperar la respuesta del esclavo.

    Usa esta herramienta cuando el usuario diga algo como 'obtén notas.txt de la PC 7 y mándamelas'.
    El archivo queda guardado en la carpeta 'archivosTransferidos' del servidor,
    listo para descargarse con GET /descargar-archivo/{nombre}.
    """
    return _ejecutar_en_loop_del_servidor(
        _obtener_archivo_de_pc_async(numero_pc, nombre_archivo, timeout),
        wait_timeout=timeout + 15,
    )


# --------------------------------------------------------------------------- #
# Vision artificial (rostros / manos)
# --------------------------------------------------------------------------- #
def detectar_rostros_pc(numero_pc: int, camara: int = 0, timeout: float = 20) -> str:
    r"""Toma una foto con la cámara de una PC esclava y detecta rostros (OpenCV).

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        camara: Índice de la cámara a usar (0 = por defecto).
        timeout: Segundos a esperar la respuesta.

    Devuelve cuántos rostros se detectaron y sus coordenadas (x, y, ancho, alto).
    Usa esta herramienta cuando el usuario pida detectar rostros o caras en una PC.
    """
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "detect_faces", {"camera_index": camara}, timeout),
        wait_timeout=timeout + 15,
    )


def detectar_manos_pc(numero_pc: int, camara: int = 0, timeout: float = 20) -> str:
    r"""Toma una foto con la cámara de una PC esclava y detecta manos (MediaPipe).

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        camara: Índice de la cámara a usar (0 = por defecto).
        timeout: Segundos a esperar la respuesta.

    Devuelve cuántas manos se detectaron, de qué mano (izquierda/derecha) y sus
    landmarks (puntos de la mano). Requiere que la PC tenga 'mediapipe' instalado.
    Usa esta herramienta cuando el usuario pida detectar manos en una PC.
    """
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "detect_hands", {"camera_index": camara}, timeout),
        wait_timeout=timeout + 15,
    )


async def _iniciar_stream_vision_async(numero_pc: int, modo: str, intervalo: float, camara: int, duracion, timeout: float) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_numero(numero_pc)
    if not agent_id:
        return f"Error: PC {numero_pc} no existe o nunca se ha conectado."
    if agent_id not in server.agents:
        info = server.agent_info.get(agent_id, {})
        return f"Error: PC {numero_pc} ({info.get('hostname', '?')}) esta desconectada."

    params = {"mode": modo, "interval": intervalo, "camera_index": camara}
    if duracion:
        params["duration"] = duracion

    try:
        resultado = await server.send_command(agent_id, "start_vision_stream", params, timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: PC {numero_pc} no respondio en {timeout}s."
    except Exception as e:
        return f"Error iniciando stream en PC {numero_pc}: {e}"

    if resultado.get("status") != "ok":
        return f"Error: {resultado.get('result')}"

    stream_id = (resultado.get("result") or {}).get("stream_id")
    if stream_id:
        server.stream_agent[stream_id] = agent_id
    return (
        f"Stream de '{modo}' iniciado en PC {numero_pc} (cada {intervalo}s). "
        f"stream_id='{stream_id}'. Usa leer_stream_vision('{stream_id}') para ver las "
        f"ultimas detecciones y detener_stream_vision('{stream_id}') para pararlo."
    )


def iniciar_stream_vision(numero_pc: int, modo: str, intervalo: float = 1.0, camara: int = 0, duracion: Optional[float] = None, timeout: float = 20) -> str:
    r"""Inicia detección continua (rostros o manos) en la cámara de una PC esclava.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        modo: 'faces' para rostros o 'hands' para manos.
        intervalo: Segundos entre cada foto/deteccion (default 1.0).
        camara: Índice de la cámara a usar (0 = por defecto).
        duracion: Segundos máximos que dura el stream (None = hasta que se detenga a mano).
        timeout: Segundos a esperar la confirmación de arranque.

    A diferencia de detectar_rostros_pc/detectar_manos_pc (una sola foto), esto deja
    a la PC mandando detecciones en vivo cada 'intervalo' segundos. Usa
    leer_stream_vision(stream_id) para consultar las últimas detecciones, y
    detener_stream_vision(stream_id) para pararlo cuando el usuario lo pida.
    Ejemplo: usuario dice 'detecta rostros en vivo en la PC 3' → iniciar_stream_vision(3, 'faces').
    """
    if modo not in ("faces", "hands"):
        return "Error: 'modo' debe ser 'faces' o 'hands'."
    return _ejecutar_en_loop_del_servidor(
        _iniciar_stream_vision_async(numero_pc, modo, intervalo, camara, duracion, timeout),
        wait_timeout=timeout + 15,
    )


async def _detener_stream_vision_async(stream_id: str, timeout: float) -> str:
    server = get_slave_server()
    agent_id = server.get_agent_id_por_stream(stream_id)
    if not agent_id:
        return f"Error: no hay un stream activo con id '{stream_id}'."
    if agent_id not in server.agents:
        return f"Error: la PC dueña del stream '{stream_id}' esta desconectada."

    try:
        resultado = await server.send_command(agent_id, "stop_vision_stream", {"stream_id": stream_id}, timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: la PC no respondio en {timeout}s."
    except Exception as e:
        return f"Error deteniendo el stream: {e}"

    server.stream_agent.pop(stream_id, None)
    if resultado.get("status") == "ok":
        return f"Stream '{stream_id}' detenido."
    return f"Error: {resultado.get('result')}"


def detener_stream_vision(stream_id: str, timeout: float = 15) -> str:
    r"""Detiene un stream de visión (rostros/manos) que esté corriendo en una PC.

    Args:
        stream_id: El id del stream devuelto por iniciar_stream_vision.
        timeout: Segundos a esperar la confirmación.
    """
    return _ejecutar_en_loop_del_servidor(
        _detener_stream_vision_async(stream_id, timeout),
        wait_timeout=timeout + 15,
    )


def leer_stream_vision(stream_id: str, n: int = 5) -> str:
    r"""Muestra las últimas detecciones de un stream de visión activo (o recién terminado).

    Args:
        stream_id: El id del stream devuelto por iniciar_stream_vision.
        n: Cuántos eventos recientes mostrar (default 5).

    Usa esta herramienta cuando el usuario pregunte 'qué está viendo la cámara',
    'cuántos rostros hay ahora', etc. sobre un stream que ya iniciaste.
    No bloquea ni espera: lee lo último que ya llegó del esclavo.
    """
    server = get_slave_server()
    eventos = server.get_stream_events(stream_id, n)
    if not eventos:
        return f"No hay eventos registrados para el stream '{stream_id}' (¿ya terminó o el id es incorrecto?)."

    lineas = [f"=== Últimos {len(eventos)} eventos de '{stream_id}' ==="]
    for ev in eventos:
        seq = ev.get("seq")
        status = ev.get("status")
        resultado = ev.get("result")
        lineas.append(f"seq {seq} [{status}]: {resultado}")
    return "\n".join(lineas)


# --------------------------------------------------------------------------- #
# Relanzar scripts ya existentes en la PC (sin pasar por Claude Code)
# --------------------------------------------------------------------------- #
def ejecutar_script_en_pc(numero_pc: int, ruta_script: str, argumentos: Optional[list] = None, segundo_plano: bool = True, timeout: float = 60) -> str:
    r"""Corre un script .py que YA existe en una PC esclava, sin invocar a Claude Code.

    Args:
        numero_pc: El número de PC (1, 2, 3...) según pcs_conectadas.
        ruta_script: Ruta del .py en esa PC (relativa a donde corre el agente, o absoluta).
        argumentos: Lista opcional de argumentos para el script.
        segundo_plano: True (default) para lanzarlo sin esperar — OBLIGATORIO para
            scripts con ventana/cámara en vivo (p. ej. uno con cv2.imshow) que el
            usuario cierra a mano, porque si no el comando se queda colgado hasta
            que cierren la ventana. False solo para scripts cortos sin ventana,
            cuando quieras su salida (stdout/stderr).
        timeout: Segundos a esperar si segundo_plano=False.

    Usa esta herramienta para RELANZAR un script que Claude ya creó y probó antes
    (vía ejecutar_claude_en_pc) — evita gastar tiempo/tokens en pedirle a Claude que
    lo regenere cada vez. Ejemplo: usuario dice 'vuelve a correr el script de
    detección de rostros en la PC 3' → ejecutar_script_en_pc(3, 'ver_rostros.py').
    """
    params = {"path": ruta_script, "background": segundo_plano}
    if argumentos:
        params["args"] = argumentos
    return _ejecutar_en_loop_del_servidor(
        _enviar_a_pc_con_respuesta_async(numero_pc, "run_script", params, timeout),
        wait_timeout=timeout + 15,
    )
