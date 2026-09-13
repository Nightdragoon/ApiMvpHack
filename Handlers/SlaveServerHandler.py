import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket


class SlaveServerHandler:
    def __init__(self):
        self.agents: dict[str, "WebSocket"] = {}
        self.pending_results: dict[str, dict] = {}
        self.agent_info: dict[str, dict] = {}
        self.numero_por_agent_id: dict[str, int] = {}
        self.agent_id_por_numero: dict[int, str] = {}
        self.next_numero: int = 1
        self._close_events: dict[str, asyncio.Event] = {}

    async def handle(self, ws: "WebSocket"):
        await ws.accept()
        try:
            hello_raw = await ws.receive_text()
        except Exception as e:
            print(f"[SLAVE] Error recibiendo hello: {e}")
            return
        try:
            hello = json.loads(hello_raw)
        except json.JSONDecodeError:
            await ws.close(code=1008, reason="hello must be JSON")
            return

        if hello.get("type") != "hello":
            await ws.close(code=1008, reason="first message must be hello")
            return

        agent_id = hello.get("agent_id")
        if not agent_id:
            await ws.close(code=1008, reason="agent_id required")
            return

        numero = self.numero_por_agent_id.get(agent_id)
        is_reconnect = agent_id in self.agents

        if is_reconnect:
            try:
                await self.agents[agent_id].close(code=1001, reason="replaced by new connection")
            except Exception:
                pass
            old_event = self._close_events.pop(agent_id, None)
            if old_event:
                old_event.set()
            pending_count = len(self.pending_results)
            if pending_count > 0:
                print(f"[SLAVE] Reconexion: clearing {pending_count} pending results")
            self.pending_results.clear()
            print(f"[SLAVE] Reemplazando conexion vieja de PC {numero} ({agent_id})")
        else:
            numero = self.next_numero
            self.next_numero += 1

        self.agents[agent_id] = ws
        self.numero_por_agent_id[agent_id] = numero
        self.agent_id_por_numero[numero] = agent_id
        self.agent_info[agent_id] = {
            "platform": hello.get("platform", "unknown"),
            "release": hello.get("release", ""),
            "hostname": hello.get("hostname", "unknown"),
            "version": hello.get("version", "unknown"),
            "connected_since": datetime.now().isoformat(),
            "numero": numero,
        }

        print(f"[SLAVE] Conectado: PC {numero} ({agent_id}) — {hello.get('hostname')}")

        close_event = asyncio.Event()
        self._close_events[agent_id] = close_event
        asyncio.create_task(self._receive_loop(ws, agent_id, close_event))
        await close_event.wait()

    async def _receive_loop(self, ws: "WebSocket", agent_id: str, close_event: asyncio.Event):
        try:
            async for raw in ws.iter_text():
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_id = msg.get("id")
                print(f"[SLAVE] Respuesta de {agent_id}: {msg}")
                if msg_id:
                    if msg_id in self.pending_results:
                        print(f"[SLAVE] DUPLICADO: cmd {msg_id} ya estaba resuelto (-race condition)")
                    else:
                        self.pending_results[msg_id] = msg
                        print(f"[SLAVE] Resultado guardado para cmd {msg_id} ({len(self.pending_results)} pendientes)")
                else:
                    print(f"[SLAVE] Respuesta sin id: {msg}")
        except Exception as e:
            print(f"[SLAVE] Error en conexion {agent_id}: {e}")
        finally:
            self._desconectar(agent_id)
            close_event.set()

    def _desconectar(self, agent_id: str):
        numero = self.numero_por_agent_id.get(agent_id)
        self.agents.pop(agent_id, None)
        self.agent_info.pop(agent_id, None)
        if numero:
            self.agent_id_por_numero.pop(numero, None)
        self.numero_por_agent_id.pop(agent_id, None)
        self._close_events.pop(agent_id, None)
        pending_count = len(self.pending_results)
        if pending_count > 0:
            print(f"[SLAVE] _desconectar: clearing {pending_count} pending results")
        self.pending_results.clear()
        print(f"[SLAVE] Desconectado: PC {numero} ({agent_id})")

    async def send_command(
        self, agent_id: str, action: str, params: Optional[dict] = None, timeout: float = 30
    ) -> dict:
        if agent_id not in self.agents:
            raise ValueError(f"PC no conectada: {agent_id}")
        ws = self.agents[agent_id]
        cmd_id = str(uuid.uuid4())
        payload = {"id": cmd_id, "action": action, "params": params or {}}
        print(f"[SLAVE] Enviando a {agent_id}: {payload}")
        print(f"[SLAVE] pending_results ANTES de enviar: {list(self.pending_results.keys())}")
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:
            self._desconectar(agent_id)
            raise ConnectionError(f"Error enviando a {agent_id}: {e}") from e

        deadline = asyncio.get_running_loop().time() + timeout
        checked_count = 0
        while asyncio.get_running_loop().time() < deadline:
            if cmd_id in self.pending_results:
                result = self.pending_results.pop(cmd_id)
                print(f"[SLAVE] Resultado para {cmd_id}: {result}")
                print(f"[SLAVE] pending_results DESPUES de resolvedor: {list(self.pending_results.keys())}")
                return result
            await asyncio.sleep(0.1)
            checked_count += 1
            if checked_count % 50 == 0:
                print(f"[SLAVE] Polling {cmd_id}: still waiting, checked={checked_count}, pending={list(self.pending_results.keys())}")

        self.pending_results.pop(cmd_id, None)
        print(f"[SLAVE] Timeout ({timeout}s) para {cmd_id} despues de {checked_count} checks")
        print(f"[SLAVE] pending_results AL TIMEOUT: {list(self.pending_results.keys())}")
        raise asyncio.TimeoutError(f"PC {agent_id} no respondió en {timeout}s")

    async def send_command_fire_and_forget(self, agent_id: str, action: str, params: Optional[dict] = None) -> bool:
        if agent_id not in self.agents:
            print(f"[SLAVE] Fire&forget: agent_id {agent_id} no conectado")
            return False
        ws = self.agents[agent_id]
        cmd_id = str(uuid.uuid4())
        payload = {"id": cmd_id, "action": action, "params": params or {}}
        print(f"[SLAVE] Fire&forget enviando a {agent_id}: {payload}")
        try:
            await ws.send_text(json.dumps(payload))
            return True
        except Exception as e:
            print(f"[SLAVE] Fire&forget error: {e}")
            self._desconectar(agent_id)
            return False

    async def send_to_all(
        self, action: str, params: Optional[dict] = None, timeout: float = 30
    ) -> dict:
        print(f"[SLAVE] send_to_all: action={action}, agents={list(self.agents.keys())}, timeout={timeout}")
        results = {}
        for agent_id in list(self.agents.keys()):
            try:
                result = await self.send_command(agent_id, action, params, timeout)
                print(f"[SLAVE] send_to_all: got result for {agent_id}: {result}")
                results[agent_id] = result
            except asyncio.TimeoutError:
                print(f"[SLAVE] send_to_all: timeout for {agent_id}")
                results[agent_id] = {"status": "error", "result": f"Timeout ({timeout}s)"}
            except Exception as e:
                print(f"[SLAVE] send_to_all: exception for {agent_id}: {type(e).__name__}: {e}")
                results[agent_id] = {"status": "error", "result": str(e)}
        print(f"[SLAVE] send_to_all: returning {results}")
        return results

    def get_pcs(self) -> list[dict]:
        pcs = []
        for agent_id, info in self.agent_info.items():
            numero = self.numero_por_agent_id.get(agent_id)
            is_online = agent_id in self.agents
            pcs.append({
                "numero": numero,
                "agent_id": agent_id,
                "hostname": info.get("hostname", "?"),
                "platform": info.get("platform", "?"),
                "release": info.get("release", ""),
                "version": info.get("version", "?"),
                "connected_since": info.get("connected_since", ""),
                "online": is_online,
            })
        return sorted(pcs, key=lambda x: x["numero"] or 999)

    def get_agent_id_por_numero(self, numero: int) -> Optional[str]:
        return self.agent_id_por_numero.get(numero)


slave_server_global: Optional[SlaveServerHandler] = None


def get_slave_server() -> SlaveServerHandler:
    global slave_server_global
    if slave_server_global is None:
        slave_server_global = SlaveServerHandler()
    return slave_server_global
