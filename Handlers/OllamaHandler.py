from ollama import chat
from ollama import ChatResponse

class OllamaHandler:
    def comunicarse_ia_no_conexion(self, prompt: str):
       response: ChatResponse = chat(model='deepseek-r1:8b', messages=[
           {
                'role': 'system',
                'content': 'Eres uzi de murderdrones y quiero que rolees como ella '
           },
            {
        
                'role': 'user',
                'content': f'{prompt}',
            },
        ] , options={
                'num_predict': 100,     # ✅ limita tokens para respuesta rápida
                'temperature': 0.7
            })
      
       return response.message.content