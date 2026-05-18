import os
from telegram import Bot
from dotenv import load_dotenv
from Handlers.DeepagentsHandler import DeepagentsHandler
from Handlers.ContextIaHandler import ContextHandler

load_dotenv(".env.local")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERNAME = "ngihtdragon"

bot = Bot(token=TOKEN) if TOKEN else None

_current_chat_id: int | None = None
_memoria = ContextHandler()

def set_current_chat_id(chat_id: int):
    global _current_chat_id
    _current_chat_id = chat_id

def get_current_chat_id() -> int | None:
    return _current_chat_id


def get_bot_info():
    if bot is None:
        return {"ok": False, "message": "TELEGRAM_BOT_TOKEN no configurado en .env.local"}
    return {"ok": True, "message": "Bot configurado"}


async def process_update(data: dict):
    handler = DeepagentsHandler()
    info = get_bot_info()
    if not info["ok"]:
        return info

    message = data.get("message")
    if not message:
        return {"ok": True, "message": "sin mensaje"}

    chat_id = message["chat"]["id"]
    chat_id_str = str(chat_id)
    username = (message.get("from") or {}).get("username", "").lower()
    text = message.get("text", "")

    print(f"[TELEGRAM] user={username}, chat={chat_id}, text='{text}'")

    if username != ALLOWED_USERNAME:
        print(f"[TELEGRAM] Usuario {username} no autorizado")
        return {"ok": True, "message": "no autorizado"}

    if text == "/start":
        await bot.send_message(chat_id=chat_id, text="Hola @ngihtdragon, estoy listo para ayudarte.")

    elif text == "/limpiar":
        _memoria.limpiar_chat(chat_id_str)
        await bot.send_message(chat_id=chat_id, text="Historial eliminado. Empezamos de cero.")

    elif text.startswith("/enviar "):
        ruta = text[8:].strip()
        if os.path.exists(ruta):
            try:
                with open(ruta, "rb") as f:
                    await bot.send_document(chat_id=chat_id, document=f)
                await bot.send_message(chat_id=chat_id, text=f"Archivo enviado: {ruta}")
            except Exception as e:
                print(f"[ERROR] /enviar: {e}")
                await bot.send_message(chat_id=chat_id, text=f"Error al enviar archivo: {e}")
        else:
            await bot.send_message(chat_id=chat_id, text=f"Archivo no encontrado: {ruta}")

    else:
        set_current_chat_id(chat_id)
        _memoria.guardar_mensaje(chat_id_str, "user", text)
        historial = _memoria.obtener_historial(chat_id_str, limite=20)
        try:
            response = handler.run(f"{text}", historial=historial, thread_id=chat_id_str)
        except Exception as e:
            print(f"[ERROR] handler.run: {e}")
            import traceback
            traceback.print_exc()
            response = f"Error interno: {e}"
        _memoria.guardar_mensaje(chat_id_str, "assistant", response)
        await bot.send_message(chat_id=chat_id, text=response)

    return {"ok": True}
