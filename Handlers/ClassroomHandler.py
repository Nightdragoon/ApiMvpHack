import os
import dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.course-work.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

ESTADOS_ENTREGADO = {"TURNED_IN", "RETURNED"}


class ClassroomHandler:

    def __init__(self):
        dotenv.load_dotenv(".env.local")
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("CLASSROOM_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("CLASSROOM_CLIENT_ID"),
            client_secret=os.getenv("CLASSROOM_CLIENT_SECRET"),
            scopes=SCOPES,
        )
        self.service = build("classroom", "v1", credentials=creds, cache_discovery=False)

    def listar_cursos(self) -> list[dict]:
        """Lista los cursos activos del usuario."""
        cursos = []
        page_token = None
        while True:
            resp = self.service.courses().list(
                courseStates=["ACTIVE"], pageToken=page_token
            ).execute()
            cursos.extend(resp.get("courses", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return [{"id": c["id"], "nombre": c["name"]} for c in cursos]

    def obtener_tareas_pendientes(self) -> list[dict]:
        """Recorre todos los cursos activos y devuelve las tareas que aún no han sido entregadas."""
        pendientes = []
        for curso in self.listar_cursos():
            course_id = curso["id"]
            page_token = None
            while True:
                resp = self.service.courses().courseWork().list(
                    courseId=course_id, courseWorkStates=["PUBLISHED"], pageToken=page_token
                ).execute()
                for tarea in resp.get("courseWork", []):
                    if self._esta_pendiente(course_id, tarea["id"]):
                        due = tarea.get("dueDate")
                        fecha_entrega = (
                            f"{due['year']}-{due['month']:02d}-{due['day']:02d}" if due else None
                        )
                        pendientes.append({
                            "curso": curso["nombre"],
                            "tarea": tarea.get("title", ""),
                            "fecha_entrega": fecha_entrega,
                            "link": tarea.get("alternateLink", ""),
                        })
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
        return pendientes

    def _esta_pendiente(self, course_id: str, coursework_id: str) -> bool:
        resp = self.service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, courseWorkId=coursework_id, userId="me"
        ).execute()
        submissions = resp.get("studentSubmissions", [])
        if not submissions:
            return True
        return submissions[0].get("state") not in ESTADOS_ENTREGADO
