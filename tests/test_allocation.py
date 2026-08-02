from src.transform.allocation import allocate_forecast_by_demand

def test_allocate_forecast_by_demand_rateio_proporcional():
    # Arrange
    forecast_values = [10, 20, 30]

    # Act
    resultado = allocate_forecast_by_demand(
        forecast_values,
        client_total_cxs=5,
        sku_total_cxs =20,
        qtd_clientes_sku=2,
    )

    # Assert
    assert resultado == [2.5, 5.0, 7.5]

def test_allocate_forecast_by_demand_fallback_defensivo():
    # Arrange
    forecast_values = [10, 20, 30]

    # Act
    resultado = allocate_forecast_by_demand(
        forecast_values,
        client_total_cxs=5,
        sku_total_cxs =0,
        qtd_clientes_sku=2,
    )

    # Assert
    assert resultado == [5.0, 10.0, 15.0]

def test_allocate_forecast_by_demand_sem_demanda():
    # Arrange
    forecast_values = [10, 20, 30]

    # Act
    resultado = allocate_forecast_by_demand(
        forecast_values,
        client_total_cxs=0,
        sku_total_cxs =0,
        qtd_clientes_sku=0,
    )

    # Assert
    assert resultado == [0.0, 0.0, 0.0]