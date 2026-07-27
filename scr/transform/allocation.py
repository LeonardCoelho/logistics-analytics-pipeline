def allocate_forecast_by_demand(
    forecast_values: list[float],
    client_total_cxs: float,
    sku_total_cxs: float,
    qtd_clientes_sku: int,
) -> list[float]:
    if sku_total_cxs > 0:
        return [client_total_cxs/sku_total_cxs * valor for valor in forecast_values]
    """
    Aloca a previsão diária de um SKU/CD para um cliente específico.

    Regra de negócio:
    - Se houver demanda total registrada para o SKU/CD (sku_total_cxs > 0),
      aloca proporcionalmente ao peso do cliente (client_total_cxs / sku_total_cxs).
    - Caso não haja demanda registrada, mas existam clientes contando esse SKU,
      divide a previsão igualmente entre eles (qtd_clientes_sku).
    - Caso nenhuma das duas condições se aplique, retorna zeros.

    Args:
        forecast_values: previsão diária do SKU/CD (mesma ordem de `day_cols`).
        client_total_cxs: total de caixas (Total CXs) desse cliente para o SKU.
        sku_total_cxs: total de caixas do SKU/CD somando todos os clientes.
        qtd_clientes_sku: quantidade de combinações loja+cliente que demandam o SKU/CD.

    Returns:
        Lista de valores alocados, no mesmo tamanho e ordem de `forecast_values`.
    """
    # TODO: implementar a lógica (equivalente ao allocate_by_demand original)
