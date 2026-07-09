"""
AntCobranzas - Sistema Integral de Gestión de Cobranzas
Desktop Admin Application
Developed by FYM Technologies
"""

import sys
import os

# Ensure the app directory is in the path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

from ui.app import run_app


if __name__ == "__main__":
    run_app()
