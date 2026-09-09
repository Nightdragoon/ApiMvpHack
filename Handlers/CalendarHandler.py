import os
import dotenv
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class CalendarHandler:

    def __init__(self):
        dotenv.load_dotenv(".env.local")
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("CALENDAR_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("CLASSROOM_CLIENT_ID"),
            client_secret=os.getenv("CLASSROOM_CLIENT_SECRET"),
            scopes=SCOPES,
        )
        self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def listar_proximos_eventos(self, max_resultados: int = 10) -> list[dict]:
        """Lista los próximos eventos del calendario principal a partir de ahora."""
        ahora = datetime.now(timezone.utc).isoformat()
        resp = self.service.events().list(
            calendarId="primary",
            timeMin=ahora,
            maxResults=max_resultados,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        eventos = []
        for e in resp.get("items", []):
            inicio = e["start"].get("dateTime", e["start"].get("date"))
            fin = e["end"].get("dateTime", e["end"].get("date"))
            eventos.append({
                "id": e["id"],
                "titulo": e.get("summary", "(sin título)"),
                "inicio": inicio,
                "fin": fin,
                "descripcion": e.get("description", ""),
                "link": e.get("htmlLink", ""),
            })
        return eventos

    def crear_evento(self, titulo: str, inicio_iso: str, fin_iso: str, descripcion: str = "",
                      zona_horaria: str = "America/Mexico_City") -> dict:
        """Crea un evento en el calendario principal. inicio_iso/fin_iso en formato ISO 8601,
        p. ej. '2026-09-10T15:00:00'."""
        evento = {
            "summary": titulo,
            "description": descripcion,
            "start": {"dateTime": inicio_iso, "timeZone": zona_horaria},
            "end": {"dateTime": fin_iso, "timeZone": zona_horaria},
        }
        creado = self.service.events().insert(calendarId="primary", body=evento).execute()
        return {
            "id": creado["id"],
            "titulo": creado.get("summary", ""),
            "inicio": creado["start"].get("dateTime"),
            "fin": creado["end"].get("dateTime"),
            "link": creado.get("htmlLink", ""),
        }
