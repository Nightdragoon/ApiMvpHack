"""Detector de rostros en vivo con OpenCV.

Script del catalogo de Uzi: se manda a un esclavo con enviar_archivo_a_pc y se
corre con ejecutar_script_en_pc (background=True, porque abre una ventana que
el usuario cierra a mano). No hace falta pedirle a Claude Code que lo genere
de nuevo cada vez.

Uso:
    python ver_rostros.py [--camera N]

Abre la camara, dibuja un rectangulo verde sobre cada rostro detectado y
muestra el conteo en pantalla. Se cierra con 'q' o ESC.

Requiere opencv-python < 5 (la version 5.x elimino CascadeClassifier y los
XML de Haar cascade del paquete).
"""

from __future__ import annotations

import argparse
import sys

import cv2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    if not hasattr(cv2, "CascadeClassifier"):
        print(
            f"Este OpenCV ({getattr(cv2, '__version__', '?')}) no trae CascadeClassifier "
            "(lo quitaron en OpenCV 5.x). Instala una version 4.x: "
            'pip install "opencv-python<5"',
            file=sys.stderr,
        )
        sys.exit(1)

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {args.camera}", file=sys.stderr)
        sys.exit(1)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
            )

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame, "Rostro", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
                )

            cv2.putText(
                frame, f"Rostros detectados: {len(faces)}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2,
            )

            cv2.imshow("Uzi - Deteccion de rostros (q o ESC para salir)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
