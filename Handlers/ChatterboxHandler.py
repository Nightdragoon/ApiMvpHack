import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from dotenv import load_dotenv
import os

class ChatterboxHandler:
    def __init__(self):
        self.model = ChatterboxTTS.from_pretrained(device="cpu")
        self.multilingual_model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
        load_dotenv(".env.local")



    def hablar(self ,text: str):
         # Multilingual examples

        wav_spanish = self.multilingual_model.generate(text, language_id="es")
        ta.save("c:/audios_fromai/test-spanish.wav", wav_spanish, self.model.sr)
        return "Hola, soy Chatterbox. ¿En qué puedo ayudarte?"