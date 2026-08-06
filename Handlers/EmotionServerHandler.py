import os

import requests
from dotenv import load_dotenv

EMOCIONES_SOPORTADAS = {"feliz", "triste", "enojado", "neutral"}


class EmotionServerHandler:
    def __init__(self):
        load_dotenv(".env.local")
        base_url = os.getenv("EMOTION_SERVER_URL", "http://localhost:8000").rstrip("/")
        self.webhook_url = f"{base_url}/webhook"

    def enviar(self, emotion: str, text: str) -> None:
        if emotion not in EMOCIONES_SOPORTADAS:
            emotion = "neutral"
        try:
            requests.post(
                self.webhook_url,
                json={"emotion": emotion, "text": text},
                timeout=2,
            )
        except Exception as e:
            print(f"[EMOTION SERVER] no se pudo enviar la emocion: {e}")
