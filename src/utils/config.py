from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

CARTEIRA_PATH = BASE_DIR / "data" / "carteira.xlsx"
PREVISAO_PATH = BASE_DIR / "data" / "previsao_recuperacao_bo.xlsx"

OUTPUT_DIR = BASE_DIR / "output"