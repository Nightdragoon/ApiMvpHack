from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import os


class ElevenLabsHandler:
    def __init__(self):
        load_dotenv(".env.local")
        self.api_key = os.environ.get("ELEVENLABS_APIKEY")
        self.client = ElevenLabs(api_key=self.api_key)
        self.voice_id = "weA4Q36twV5kwSaTEL0Q"  # robo voz)
        self.output_path = "c:/audios_fromai/elevenlabs_output.mp3"

    def generar_audio(self, text: str) -> str:
        audio_stream = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        with open(self.output_path, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)

        return self.output_path
