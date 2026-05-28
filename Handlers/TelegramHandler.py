import os
from telegram import Bot
from dotenv import load_dotenv
from Handlers.DeepagentsHandler import DeepagentsHandler
from Handlers.ContextIaHandler import ContextHandler
import whisper

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

    voice = message.get("voice")
    if voice:
        try:
            file = await bot.get_file(voice["file_id"])
            os.makedirs("c:/audios_fromai", exist_ok=True)
            ruta_ogg = f"c:/audios_fromai/voice_{voice['file_id']}.ogg"
            await file.download_to_drive(ruta_ogg)
            modelo = whisper.load_model("base")
            resultado = modelo.transcribe(ruta_ogg)
            text = resultado["text"].strip()
            os.remove(ruta_ogg)
            print(f"[TELEGRAM] voz transcrita: '{text}'")
        except Exception as e:
            print(f"[ERROR] transcripcion voz: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error al procesar voz: {e}")
            return {"ok": True, "message": "error voz"}

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

        total = _memoria.contar_mensajes(chat_id_str)
        memoria_larga = _memoria.obtener_memoria_largoplazo(chat_id_str)

        if total >= 6:
            ultimos_6 = _memoria.obtener_historial(chat_id_str, limite=6)
            texto_resumen = "\n".join(f"{m['rol']}: {m['contenido']}" for m in ultimos_6)
            try:
                resumen = handler.generate_summary(texto_resumen)
                _memoria.actualizar_memoria_largoplazo(chat_id_str, resumen)
                _memoria.eliminar_ultimos_n_mensajes(chat_id_str, 6)
                memoria_larga = resumen
                print(f"[MEMORIA] Resumen generado y guardado para chat {chat_id_str}")
            except Exception as e:
                print(f"[ERROR] generando resumen: {e}")

        historial = _memoria.obtener_historial(chat_id_str, limite=20)
        try:
            response = handler.run(f"{text}", historial=historial, thread_id=chat_id_str, memoria_largoplazo=memoria_larga)
        except Exception as e:
            print(f"[ERROR] handler.run: {e}")
            import traceback
            traceback.print_exc()
            response = f"Error interno: {e}"
        _memoria.guardar_mensaje(chat_id_str, "assistant", response)
        await bot.send_message(chat_id=chat_id, text=response)

    return {"ok": True}
