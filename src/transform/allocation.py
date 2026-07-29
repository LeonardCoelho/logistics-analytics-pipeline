def allocate_forecast_by_demand(
    forecast_values: list[float],
    client_total_cxs: float,
    sku_total_cxs: float,
    qtd_clientes_sku: int,
) -> list[float]:
    if sku_total_cxs > 0:
        return [client_total_cxs/sku_total_cxs * valor for valor in forecast_values]
    elif qtd_clientes_sku > 0:
        return [valor/qtd_clientes_sku for valor in forecast_values]
    return len(forecast_values) * [0.0]

if __name__ == "__main__":
    # Caso 1: rateio proporcional
    print(allocate_forecast_by_demand([10, 20, 30], client_total_cxs=5, sku_total_cxs=20, qtd_clientes_sku=2))
    # esperado: [2.5, 5.0, 7.5]

    # Caso 2: fallback defensivo (divisão igualitária)
    print(allocate_forecast_by_demand([10, 20, 30], client_total_cxs=5, sku_total_cxs=0, qtd_clientes_sku=2))
    # esperado: [5.0, 10.0, 15.0]

    # Caso 3: sem demanda nenhuma
    print(allocate_forecast_by_demand([10, 20, 30], client_total_cxs=0, sku_total_cxs=0, qtd_clientes_sku=0))
    # esperado: [0.0, 0.0, 0.0]