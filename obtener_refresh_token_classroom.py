"""
Script de un solo uso: genera el refresh_token de Classroom.

1. Descarga client_secret.json desde Google Cloud Console (Credenciales > ID de
   cliente OAuth > tipo "App de escritorio") y ponlo en la raíz del proyecto.
2. Corre: python obtener_refresh_token_classroom.py
3. Se abre el navegador, inicia sesión con tu cuenta de Google y acepta.
4. Copia el CLASSROOM_CLIENT_ID, CLASSROOM_CLIENT_SECRET y CLASSROOM_REFRESH_TOKEN
   que se imprimen al final a tu .env.local.

Este script no se vuelve a necesitar salvo que revoques el acceso.
"""
import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.course-work.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
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
    print(f"CLASSROOM_CLIENT_ID={creds.client_id}")
    print(f"CLASSROOM_CLIENT_SECRET={creds.client_secret}")
    print(f"CLASSROOM_REFRESH_TOKEN={creds.refresh_token}")
