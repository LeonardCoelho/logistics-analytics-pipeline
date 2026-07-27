import pandas as pd

def load_carteira(path):
    return pd.read_excel(path, engine="openpyxl", header=2)

def load_previsao(path):
    return pd.read_excel(path, engine="openpyxl")