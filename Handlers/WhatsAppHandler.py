import re
import requests
import json

EVOLUTION_API_URL = "http://localhost:8080"
EVOLUTION_INSTANCE = "prueba"
EVOLUTION_APIKEY = "429683C4C977415CAAFCCE10F7D57E11"


def _extraer_texto(message: dict) -> str:
    if "conversation" in message:
        return message["conversation"]
    if "extendedTextMessage" in message:
        return message["extendedTextMessage"].get("text", "")
    if "imageMessage" in message:
        return message["imageMessage"].get("caption", "")
    if "videoMessage" in message:
        return message["videoMessage"].get("caption", "")
    return ""


def _contiene_mencion(texto: str) -> bool:
    return bool(re.search(r'@uzi', texto, re.IGNORECASE))


def _limpiar_mencion(texto: str) -> str:
    return re.sub(r'@uzi\s*', '', texto, flags=re.IGNORECASE).strip()


def _enviar_whatsapp(numero: str, mensaje: str) -> str:
    numero_limpio = re.sub(r'\D', '', numero)
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_APIKEY
    }
    body = {
        "number": numero_limpio,
        "text": mensaje
    }
    response = requests.post(url, json=body, headers=headers)
    return json.dumps({"status_code": response.status_code, "response": response.text}, ensure_ascii=False)


def process_whatsapp_event(event_data: dict, handler) -> dict:
    try:
        print(f"[WHATSAPP] PAYLOAD COMPLETO: {json.dumps(event_data, ensure_ascii=False, default=str)[:3000]}")

        if event_data.get("event") != "messages.upsert":
            return {"ok": True, "message": "evento ignorado"}

        data = event_data.get("data", {})
        if not data:
            data = event_data  # fallback si no hay anidacion

        key = data.get("key", {})

        if key.get("fromMe", False):
            return {"ok": True, "message": "mensaje propio ignorado"}

        remote_jid = key.get("remoteJid", "")
        if not remote_jid:
            return {"ok": True, "message": "sin remoteJid"}

        numero = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")
        push_name = data.get("pushName", "Desconocido")
        message = data.get("message", {})
        texto = _extraer_texto(message)

        print(f"[WHATSAPP] numero={numero}, pushName={push_name}, texto='{texto}'")

        if not texto or not _contiene_mencion(texto):
            return {"ok": True, "message": "sin mencion"}

        prompt = _limpiar_mencion(texto)
        print(f"[WHATSAPP] Mensaje de {numero} ({push_name}): '{texto}' -> prompt: '{prompt}'")

        respuesta = handler.run(prompt)
        print(f"[WHATSAPP] Respuesta para {numero}: '{respuesta[:100]}...'")

        _enviar_whatsapp(numero, respuesta)

        return {"ok": True, "message": "respondido", "to": numero}

    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": str(e)}


def set_evolution_webhook(webhook_url: str) -> dict:
    try:
        url = f"{EVOLUTION_API_URL}/webhook/set/{EVOLUTION_INSTANCE}"
        headers = {
            "Content-Type": "application/json",
            "apikey": EVOLUTION_APIKEY
        }
        body = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "webhook_by_events": False,
                "webhook_base64": False,
                "events": ["MESSAGES_UPSERT"]
            }
        }
        response = requests.post(url, json=body, headers=headers)
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "response": response.text
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}
