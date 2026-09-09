"""
Script de un solo uso: genera el refresh_token de Google Calendar.

Reutiliza el mismo client_secret.json que ya usaste para Classroom (mismo proyecto
de Google Cloud), solo pide un refresh_token nuevo con los scopes de Calendar.

1. Asegúrate de tener client_secret.json en la raíz del proyecto (el mismo de Classroom).
2. En la consola de Google Cloud, en "Datos de acceso" de la pantalla de consentimiento,
   agrega y marca los scopes de Calendar:
     .../auth/calendar.readonly
     .../auth/calendar.events
3. Corre: python obtener_refresh_token_calendar.py
4. Se abre el navegador, inicia sesión y acepta (marca los 2 checkboxes de Calendar).
5. Copia el CALENDAR_REFRESH_TOKEN que se imprime al final a tu .env.local.
   (CLASSROOM_CLIENT_ID y CLASSROOM_CLIENT_SECRET ya los tienes de Classroom y se reutilizan).
"""
import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    otorgados = set(creds.scopes or [])
    faltantes = [s for s in SCOPES if s not in otorgados]
    if faltantes:
        print("\nATENCION: no se otorgaron todos los permisos. Faltan:")
        for s in faltantes:
            print(f"  - {s}")
        print("Vuelve a correr el script y asegurate de marcar TODOS los checkboxes de permisos.\n")

    print("\nAgrega esto a tu .env.local:\n")
    print(f"CALENDAR_REFRESH_TOKEN={creds.refresh_token}")
