-- Estructura optimizada para Ventas Generales y Visualizador general de clientes.
-- No modifica el modulo de forecast.
-- Pensado para SQL Server. Si se usa PostgreSQL/MySQL, ajustar tipos e indices include.

CREATE TABLE dbo.fact_ventas_dashboard (
    anio SMALLINT NOT NULL,
    semana_iso TINYINT NOT NULL,
    anio_semana CHAR(8) NOT NULL,
    cod_cliente VARCHAR(32) NOT NULL,
    cliente NVARCHAR(180) NULL,
    NomCompania NVARCHAR(180) NULL,
    pais NVARCHAR(120) NULL,
    producto NVARCHAR(120) NULL,
    color NVARCHAR(80) NULL,
    tipo_pedido_operativo VARCHAR(40) NULL,
    sku_operativo NVARCHAR(320) NULL,
    caja_operativa VARCHAR(80) NULL,
    pedido VARCHAR(80) NULL,
    tallos_confirmados DECIMAL(18, 2) NOT NULL,
    tallos_pedidos DECIMAL(18, 2) NOT NULL,
    ventas_usd DECIMAL(18, 4) NOT NULL,
    valor_total_original DECIMAL(18, 4) NOT NULL,
    moneda_original VARCHAR(16) NULL
);

CREATE INDEX IX_fact_ventas_dashboard_semana
ON dbo.fact_ventas_dashboard (anio, semana_iso)
INCLUDE (tallos_confirmados, ventas_usd, cod_cliente, producto);

CREATE INDEX IX_fact_ventas_dashboard_cliente
ON dbo.fact_ventas_dashboard (cod_cliente, anio, semana_iso)
INCLUDE (cliente, producto, color, tipo_pedido_operativo, sku_operativo, tallos_confirmados, tallos_pedidos, ventas_usd);

CREATE INDEX IX_fact_ventas_dashboard_producto
ON dbo.fact_ventas_dashboard (producto, anio, semana_iso)
INCLUDE (cod_cliente, tallos_confirmados, ventas_usd);

CREATE INDEX IX_fact_ventas_dashboard_pais
ON dbo.fact_ventas_dashboard (pais, anio, semana_iso)
INCLUDE (cod_cliente, producto, tallos_confirmados, ventas_usd);

CREATE INDEX IX_fact_ventas_dashboard_sku
ON dbo.fact_ventas_dashboard (sku_operativo, anio, semana_iso)
INCLUDE (cod_cliente, tipo_pedido_operativo, producto, color, tallos_confirmados, tallos_pedidos, ventas_usd);

CREATE VIEW dbo.vw_ventas_generales_semana_cliente_producto AS
SELECT
    anio,
    semana_iso,
    anio_semana,
    cod_cliente,
    MAX(cliente) AS cliente,
    MAX(NomCompania) AS NomCompania,
    MAX(pais) AS pais,
    producto,
    MAX(moneda_original) AS moneda_original,
    SUM(tallos_confirmados) AS tallos_confirmados,
    SUM(ventas_usd) AS ventas_usd,
    SUM(valor_total_original) AS valor_total_original,
    COUNT(DISTINCT pedido) AS pedidos,
    COUNT(DISTINCT caja_operativa) AS cajas_ids,
    CAST(SUM(ventas_usd) / NULLIF(SUM(tallos_confirmados), 0) AS DECIMAL(18, 6)) AS precio_usd_tallo,
    CAST(SUM(valor_total_original) / NULLIF(SUM(tallos_confirmados), 0) AS DECIMAL(18, 6)) AS precio_moneda_original_tallo
FROM dbo.fact_ventas_dashboard
GROUP BY anio, semana_iso, anio_semana, cod_cliente, producto;

CREATE VIEW dbo.vw_visualizador_cliente_sku_semana AS
SELECT
    anio,
    semana_iso,
    anio_semana,
    cod_cliente,
    MAX(cliente) AS cliente,
    MAX(NomCompania) AS NomCompania,
    MAX(pais) AS pais,
    tipo_pedido_operativo,
    sku_operativo,
    producto,
    color,
    SUM(tallos_confirmados) AS tallos_confirmados,
    SUM(tallos_pedidos) AS tallos_pedidos,
    SUM(ventas_usd) AS ventas_usd,
    COUNT(DISTINCT pedido) AS pedidos,
    COUNT(DISTINCT caja_operativa) AS cajas,
    CAST(SUM(ventas_usd) / NULLIF(SUM(tallos_confirmados), 0) AS DECIMAL(18, 6)) AS precio_usd_tallo,
    CAST(SUM(tallos_confirmados) / NULLIF(SUM(tallos_pedidos), 0) AS DECIMAL(18, 6)) AS cumplimiento
FROM dbo.fact_ventas_dashboard
GROUP BY anio, semana_iso, anio_semana, cod_cliente, tipo_pedido_operativo, sku_operativo, producto, color;
