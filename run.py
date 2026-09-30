"""Point d'entrée hors-ligne — aucune connexion requise."""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.main import main

if __name__ == "__main__":
    main()
