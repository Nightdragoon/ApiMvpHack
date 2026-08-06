# Cómo tu IA avisa al Emotion Server

Este documento explica cómo este backend (la IA, `ApiMvpHack`) le comunica al
proyecto **Emotion Server** qué emoción debe mostrar en su display cada vez que
el agente responde.

> El Emotion Server es el proyecto que recibe eventos de emoción por HTTP y los
> muestra (ícono + texto + animación) en una pestaña de navegador. No hace falta
> tocar nada de ese repo desde acá: la IA solo hace un `POST` a su webhook.

## Cómo está implementado

- La IA responde desde `DeepagentsHandler.run()` (`Handlers/DeepagentsHandler.py`).
  Ese método lo usan los 3 canales: el endpoint `/deepagents`, el bot de
  WhatsApp y el bot de Telegram.
- El agente tiene una herramienta `registrar_emotion` que está **forzada a usar
  en cada turno** (`tool_choice="registrar_emotion"` en el primer paso del
  grafo). El modelo devuelve la emoción como argumento estructurado de esa
  llamada — no escribe JSON en el texto visible, así que la respuesta al
  usuario siempre es texto plano.
- `registrar_emotion` hace el `POST` al webhook del Emotion Server, y
  `run()` reenvía el evento con la emoción elegida por la IA y el texto real de
  la respuesta (por si el primer envío ocurrió antes de conocer el texto final).
- Si por algún motivo el modelo no llegara a llamar la herramienta, se envía
  `neutral` como respaldo para que el display igual se actualice.

## Configuración

En `.env.local`:

```
EMOTION_SERVER_URL=http://localhost:8000
```

Si el Emotion Server corre en otra máquina de tu red, cambiá esa URL a
`http://<IP>:8000`. Si no está seteada, el valor por defecto es
`http://localhost:8000`.

## Endpoint que usa la IA

```
POST http://<IP>:8000/webhook
Content-Type: application/json
```

Payload:

```json
{
  "emotion": "feliz",
  "text": "saludos humano"
}
```

| Campo     | Tipo   | Descripción                                          |
|-----------|--------|-------------------------------------------------------|
| `emotion` | string | Una de: `feliz`, `triste`, `enojado`, `neutral`       |
| `text`    | string | El texto de la respuesta, que se muestra y se lee    |

> Otras emociones del contrato original (`sorprendido`, `amor`, `miedo`,
> `confundido`) no tienen ícono todavía en el Emotion Server; por eso la IA solo
> manda las 4 que sí se distinguen visualmente.

## En qué respuestas se dispara

En **todas** las respuestas de `DeepagentsHandler.run()`:

- `GET /deepagents?text=...` (devuelve el audio).
- Mensajes de WhatsApp (vía `/whatsapp-webhook`).
- Mensajes de Telegram (vía `/telegram-webhook`).

## Notas

- Es *best-effort*: si el Emotion Server no está corriendo, el `POST` falla
  silenciosamente y la IA responde igual (timeout de 2 segundos).
- No hay autenticación en el webhook; solo usarlo en red local, no exponerlo a
  internet.
- Si nadie está conectado al display por WebSocket cuando llega el evento, el
  servidor guarda el último estado y se lo manda al próximo cliente que se
  conecte.
