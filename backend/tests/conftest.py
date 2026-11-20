"""Configuración de imports compartida por las pruebas del backend.

Permite ejecutar pytest desde la raíz del repositorio o desde otra carpeta
sin tener que instalar el backend como paquete.
"""
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
