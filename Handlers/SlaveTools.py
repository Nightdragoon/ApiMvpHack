import asyncio
from typing import Optional

from Handlers.SlaveServerHandler import get_slave_server


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


def _ejecutar_en_loop_del_servidor(coro):
    """Ejecuta una corrutina en el event loop principal del servidor.

    Las tools del modelo corren en un hilo aparte. El WebSocket vive en el
    loop principal, asi que NO podemos usar asyncio.run() (crearia un loop
    nuevo y el send cruzaria event loops, corrompiendo el socket). En su
    lugar agendamos la corrutina en el loop principal y esperamos el
    resultado desde este hilo.
    """
    server = get_slave_server()
    loop = server.loop
    if loop is not None and loop.is_running():
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result(timeout=35)
    # Fallback: no hay loop del servidor todavia (ninguna PC conectada aun).
    return asyncio.run(coro)


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
