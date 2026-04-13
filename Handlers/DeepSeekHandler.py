from dotenv import load_dotenv
import os

from openai import OpenAI


class DeepSeekHandler:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get("DEEPSEEK_APIKEY")
    
    def comunicarse_ia(self, prompt: str):
        # Aquí iría la lógica para comunicarse con la API de DeepSeek utilizando self.api_key
        # Por ejemplo, podrías hacer una solicitud HTTP a la API de DeepSeek con el prompt y la clave de API
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "eres uzi de murderdrones y quiero que rolees como ella "},
                {"role": "user", "content": f"{prompt}"},
            ],
            stream=False,
            max_tokens=100
        )
        return response.choices[0].message.content
    
    def comunicarse_ia_audio(self, prompt: str):
        # Aquí iría la lógica para comunicarse con la API de DeepSeek utilizando self.api_key
        # Por ejemplo, podrías hacer una solicitud HTTP a la API de DeepSeek con el prompt y la clave de API
        client = OpenAI(self.api_key, base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "eres uzi de murderdrones y quiero que rolees como ella "},
                {"role": "user", "content": f"{prompt}"},
            ],
            stream=False
        )
        return f"Respuesta de DeepSeek para el prompt: {prompt}"
    