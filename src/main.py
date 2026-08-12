import pandas as pd
import numpy as np
from datetime import datetime
from extract.extract import load_carteira, load_previsao
from transform.allocation import allocate_forecast_by_demand
from utils.config import CARTEIRA_PATH, PREVISAO_PATH, OUTPUT_DIR

# Ler bases
carteira = load_carteira(CARTEIRA_PATH)
previsao = load_previsao(PREVISAO_PATH)

# Padronizar nomes
carteira["2º No.Item"] = carteira["2º No.Item"].astype("Int64").astype(str).str.strip()
carteira["CD"] = carteira["CD"].astype(str).str.strip().str.upper()

previsao["codigo_sku"] = previsao["codigo_sku"].astype("Int64").astype(str).str.strip()
previsao["cd"] = previsao["cd"].astype(str).str.strip().str.upper()

# Filtrar BO da tabela de frequência > 7 dias
bo = carteira[
    (carteira["Age Log"] > 7) &
    (carteira["Status Final(Lista)"] == "PEDIDOS BAIXO VOLUME (TABELA DE FREQUENCIA)")
].copy()
# --- Alocação de previsão por SKU para clientes (divisão igualitária) ---

# identificar colunas de dias na previsão (1..31)
day_cols = [c for c in previsao.columns if c.isdigit()]

# agrega previsão por SKU e CD (soma caso haja duplicados)
previsao_agg = previsao.groupby(["codigo_sku", "cd"], as_index=False)[day_cols].sum()

# agregar demanda por cliente+sku a partir dos BO filtrados (incluir CD de origem)
demanda = bo.groupby(["2º No.Item", "CD", "Cód. Loja", "Cliente filho"], as_index=False)["Total CXs"].sum()

# contar quantas combinações loja+cliente demandam cada SKU por CD
clients_per_sku = demanda.groupby(["2º No.Item", "CD"], as_index=False).agg(qtd_clientes_sku=("Cliente filho", "size"))

demanda = demanda.merge(clients_per_sku, on=["2º No.Item", "CD"], how="left")

# juntar a previsão total do SKU com a demanda cliente-sku, respeitando o CD de recuperação
demanda = demanda.merge(previsao_agg, left_on=["2º No.Item", "CD"], right_on=["codigo_sku", "cd"], how="left")

# preservar previsão original por dia para cálculo de recuperação baseado no SKU/CD
forecast_cols = []
for d in day_cols:
    forecast_col = f"forecast_{d}"
    demanda[forecast_col] = demanda[d].fillna(0)
    forecast_cols.append(forecast_col)

# adicionar descrição do SKU (vinda da carteira original) - detectar coluna dinamicamente
import unicodedata

def _norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c)).lower()

# encontrar colunas que contenham 'descr'
candidates = [c for c in carteira.columns if 'descr' in _norm(c)]
descr_col = None
if candidates:
    # preferir coluna cujo nome normalizado seja exatamente 'descricao'
    for c in candidates:
        if _norm(c).strip() == 'descricao':
            descr_col = c
            break

    # se não encontrou, preferir candidato que não contenha 'canal'
    if not descr_col:
        non_canal = [c for c in candidates if 'canal' not in _norm(c)]
        if non_canal:
            # escolher o nome mais curto (provavelmente 'Descrição')
            descr_col = sorted(non_canal, key=lambda x: len(x))[0]
        else:
            # fallback: primeiro candidato
            descr_col = candidates[0]

if descr_col:
    sku_descr = carteira[["2º No.Item", descr_col]].drop_duplicates(subset=["2º No.Item"]).rename(columns={descr_col: "SKU Descrição"})
    demanda = demanda.merge(sku_descr, left_on=["2º No.Item"], right_on=["2º No.Item"], how="left")
else:
    demanda["SKU Descrição"] = None

# preencher NaNs das colunas de dias com zero
for d in day_cols:
    demanda[d] = demanda[d].fillna(0)

# total de previsão do SKU antes da alocação
if "Previsao Total SKU" not in demanda.columns:
    demanda["Previsao Total SKU"] = demanda[day_cols].sum(axis=1)

# total de CXs por SKU+CD para alocação proporcional
demanda["sku_total_cxs"] = demanda.groupby(["2º No.Item", "CD"])["Total CXs"].transform("sum")

# aplicar valores alocados de volta às colunas de dias
alloc_values = demanda.apply(lambda r: allocate_forecast_by_demand(client_total_cxs=r["Total CXs"], sku_total_cxs=r["sku_total_cxs"], qtd_clientes_sku=r["qtd_clientes_sku"], forecast_values=[r[d] for d in day_cols]), axis=1)
alloc_df = pd.DataFrame(alloc_values.tolist(), columns=day_cols)
demanda[day_cols] = alloc_df[day_cols]

# calcular recuperação de cada SKU + CD + cliente usando previsão original do SKU/CD
hoje = datetime.now()
dia_hoje = hoje.day
dias = [d for d in day_cols if int(d) >= dia_hoje]

def calcular_recuperacao_sku(row):
    acumulado = 0
    for dia in dias:
        valor = row.get(f"forecast_{dia}", 0)
        if pd.isna(valor):
            valor = 0
        acumulado += valor
        if acumulado >= row["Total CXs"]:
            return f"D+{int(dia) - dia_hoje}", acumulado, int(dia)
    return "Sem previsão até fim do mês", acumulado, np.nan

recuperacao_sku = demanda.apply(calcular_recuperacao_sku, axis=1, result_type='expand')
demanda["sku_recuperacao_dia"] = recuperacao_sku[2]

def any_missing_sku_recuperacao(series):
    return series.isna().any()

# preparar base de recuperação no nível cliente + CD
base = demanda.groupby(["Cód. Loja", "Cliente filho", "CD"], as_index=False).agg(
    Total_CXs=("Total CXs", "sum"),
    **{d: (d, "sum") for d in day_cols}
)

# calcular D+ do maior SKU por cliente+CD
sku_recuperacao_meta = demanda.groupby(["Cód. Loja", "Cliente filho", "CD"], as_index=False).agg(
    max_sku_recuperacao_dia=("sku_recuperacao_dia", "max")
)
base = base.merge(sku_recuperacao_meta, on=["Cód. Loja", "Cliente filho", "CD"], how="left")

# Obter o dia de hoje e montar lista de dias a partir de hoje presentes na base
hoje = datetime.now()
dia_hoje = hoje.day
dias = [d for d in day_cols if int(d) >= dia_hoje]

def calcular_recuperacao(row):
    if pd.isna(row["max_sku_recuperacao_dia"]):
        return "Sem previsão até fim do mês", 0

    dia_recuperacao = int(row["max_sku_recuperacao_dia"])
    if dia_recuperacao < dia_hoje:
        dia_recuperacao = dia_hoje

    acumulado = 0
    for dia in dias:
        if int(dia) > dia_recuperacao:
            break
        valor = row.get(dia, 0)
        if pd.isna(valor):
            valor = 0
        acumulado += valor

    diferenca = dia_recuperacao - dia_hoje
    return f"D+{diferenca}", acumulado

recuperacao_info = base.apply(calcular_recuperacao, axis=1, result_type='expand')
base["Previsão Recuperação"] = recuperacao_info[0]
base["CXs Previsão Recuperação"] = recuperacao_info[1]

# Arredondar previsão de recuperação para inteiro (valor mais próximo)
base["CXs Previsão Recuperação"] = base["CXs Previsão Recuperação"].fillna(0).round().astype(int)

# Colunas finais (nível cliente + CD)
saida = base[
    [
        "Cód. Loja",
        "Cliente filho",
        "CD",
        "Total_CXs",
        "Previsão Recuperação",
        "CXs Previsão Recuperação"
    ]
].rename(columns={
    "Total_CXs": "Total CXs"
})

# Exportar
import os
arquivo_saida = "output/resultado_bo.xlsx"
if os.path.exists(arquivo_saida):
    os.remove(arquivo_saida)
saida.to_excel(arquivo_saida, index=False)
print(f"OK - Arquivo exportado com sucesso: {arquivo_saida}")

# Exportar também arquivo com SKUs por cliente (demanda e previsão alocada)
# garantir formato consistente de SKU (string sem '.0')
demanda["2º No.Item"] = demanda["2º No.Item"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

skus = demanda[["Cód. Loja", "Cliente filho", "CD", "2º No.Item", "SKU Descrição", "Total CXs", "qtd_clientes_sku"]].copy()

# calcular recuperação por SKU + CD + cliente até o D+ de recuperação usando previsão original do SKU/CD
hoje = datetime.now()
dia_hoje = hoje.day
dias = [d for d in day_cols if int(d) >= dia_hoje]

recuperacao_sku = demanda.apply(calcular_recuperacao_sku, axis=1, result_type='expand')
demanda["sku_recuperacao_dia"] = recuperacao_sku[2]
skus["Previsão Recuperação"] = recuperacao_sku[0]
skus["CXs Previsão Recuperação"] = recuperacao_sku[1].fillna(0).round().astype(int)

# preparar mapa SKU -> descrição (toda a carteira) para referência
if 'descr_col' in globals() and descr_col:
    sku_map = carteira[["2º No.Item", descr_col]].drop_duplicates(subset=["2º No.Item"]).rename(columns={descr_col: "SKU Descrição"})
else:
    sku_map = carteira[["2º No.Item"]].drop_duplicates(subset=["2º No.Item"]) 

# normalizar formato do SKU no mapa (string sem .0)
sku_map["2º No.Item"] = sku_map["2º No.Item"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

# Incluir também SKUs sem demanda (para referência) — manter Loja/Cliente vazios e zeros
sku_map_export = sku_map.copy()
sku_map_export["2º No.Item"] = sku_map_export["2º No.Item"].astype(str)
missing = sku_map_export[~sku_map_export["2º No.Item"].isin(skus["2º No.Item"])].copy()
if not missing.empty:
    missing = missing.rename(columns={"SKU Descrição": "SKU Descrição"})
    missing["Cód. Loja"] = None
    missing["Cliente filho"] = None
    missing["CD"] = None
    missing["Total CXs"] = 0
    missing["qtd_clientes_sku"] = 0
    missing["Previsão Recuperação"] = None
    missing["CXs Previsão Recuperação"] = 0
    missing = missing[["Cód. Loja", "Cliente filho", "CD", "2º No.Item", "SKU Descrição", "Total CXs", "qtd_clientes_sku", "Previsão Recuperação", "CXs Previsão Recuperação"]]
    skus_all = pd.concat([skus, missing], ignore_index=True, sort=False)
else:
    skus_all = skus

arquivo_skus = "output/skus_por_cliente.xlsx"
if os.path.exists(arquivo_skus):
    os.remove(arquivo_skus)
# Garantir que '2º No.Item' seja texto no Excel (remover .0)
skus_all["2º No.Item"] = skus_all["2º No.Item"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
skus_all.to_excel(arquivo_skus, index=False)
print(f"OK - Arquivo exportado com sucesso: {arquivo_skus}")

arquivo_sku_map = "output/sku_descriptions.xlsx"
if os.path.exists(arquivo_sku_map):
    os.remove(arquivo_sku_map)
# Normalizar SKU no mapa (remover .0)
sku_map["2º No.Item"] = sku_map["2º No.Item"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
sku_map.to_excel(arquivo_sku_map, index=False)
print(f"OK - Arquivo exportado com sucesso: {arquivo_sku_map}")