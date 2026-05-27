/*
LGF - Esquema SQL sugerido para MVP analítico-operativo.
SQL Server.

Regla de estados:
- Confirmado = histórico real despachado.
- Pendiente = orden real futura recibida del cliente.
- En proceso = estimado comercial.
- Por verificar/Reproceso = cambios sobre algo ya confirmado.
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'lgf_analytics')
    EXEC('CREATE SCHEMA lgf_analytics');
GO

CREATE TABLE lgf_analytics.fact_pedido_operativo (
    id_pedido_operativo BIGINT IDENTITY(1,1) PRIMARY KEY,
    fecha DATE NOT NULL,
    anio INT NULL,
    semana_iso INT NULL,
    anio_semana VARCHAR(10) NULL,
    mes_num INT NULL,
    dia_semana_num INT NULL,
    cod_cliente NVARCHAR(100) NOT NULL,
    cliente NVARCHAR(255) NOT NULL,
    cliente_key NVARCHAR(400) NULL,
    subcliente NVARCHAR(255) NULL,
    producto NVARCHAR(100) NULL,
    variedad NVARCHAR(150) NULL,
    color NVARCHAR(100) NULL,
    grado NVARCHAR(50) NULL,
    tipo_caja NVARCHAR(50) NULL,
    tallos_x_ramo NVARCHAR(50) NULL,
    empaque NVARCHAR(255) NULL,
    capuchon NVARCHAR(255) NULL,
    comida NVARCHAR(255) NULL,
    pais NVARCHAR(100) NULL,
    ciudad NVARCHAR(100) NULL,
    finca NVARCHAR(100) NULL,
    tipo_orden NVARCHAR(100) NULL,
    tipo_orden_empaque NVARCHAR(100) NULL,
    estado NVARCHAR(100) NULL,
    estado_canonico NVARCHAR(50) NULL,
    estado_categoria NVARCHAR(100) NULL,
    es_historico_real BIT NULL,
    es_orden_real_futura BIT NULL,
    es_estimado_comercial BIT NULL,
    es_cambio_sobre_confirmado BIT NULL,
    tallos_pedidos DECIMAL(18,4) NULL,
    tallos_confirmados DECIMAL(18,4) NULL,
    tallos_analisis DECIMAL(18,4) NULL,
    faltante_tallos DECIMAL(18,4) NULL,
    cumplimiento_linea DECIMAL(18,6) NULL,
    sku_terminado NVARCHAR(800) NULL,
    sku_flexible NVARCHAR(500) NULL,
    producto_color NVARCHAR(300) NULL,
    producto_variedad_color NVARCHAR(500) NULL,
    empaque_operativo NVARCHAR(800) NULL,
    fecha_carga DATETIME2 DEFAULT SYSDATETIME()
);
GO

CREATE INDEX IX_fact_pedido_operativo_codcliente_fecha
ON lgf_analytics.fact_pedido_operativo(cod_cliente, fecha);
GO

CREATE INDEX IX_fact_pedido_operativo_estado_fecha
ON lgf_analytics.fact_pedido_operativo(estado_canonico, fecha);
GO

CREATE INDEX IX_fact_pedido_operativo_sku
ON lgf_analytics.fact_pedido_operativo(sku_terminado, fecha);
GO

CREATE TABLE lgf_analytics.perfil_cliente (
    cod_cliente NVARCHAR(100) NOT NULL,
    cliente NVARCHAR(255) NOT NULL,
    semanas_activas INT NULL,
    semanas_observadas_global INT NULL,
    pct_semanas_activas DECIMAL(18,6) NULL,
    tallos_total DECIMAL(18,4) NULL,
    tallos_promedio_semana DECIMAL(18,4) NULL,
    tallos_mediana_semana DECIMAL(18,4) NULL,
    cv_volumen DECIMAL(18,6) NULL,
    cumplimiento_tallos DECIMAL(18,6) NULL,
    incumplimiento_tallos DECIMAL(18,6) NULL,
    share_top3_color DECIMAL(18,6) NULL,
    share_top5_sku_terminado DECIMAL(18,6) NULL,
    share_top3_empaque DECIMAL(18,6) NULL,
    score_frecuencia DECIMAL(18,4) NULL,
    score_volumen DECIMAL(18,4) NULL,
    score_color DECIMAL(18,4) NULL,
    score_sku_terminado DECIMAL(18,4) NULL,
    score_empaque DECIMAL(18,4) NULL,
    score_oportunidad_incumplimiento DECIMAL(18,4) NULL,
    score_compra_terminada DECIMAL(18,4) NULL,
    segmento_cliente NVARCHAR(100) NULL,
    recomendacion_compra NVARCHAR(100) NULL,
    fecha_calculo DATETIME2 DEFAULT SYSDATETIME(),
    CONSTRAINT PK_perfil_cliente PRIMARY KEY (cod_cliente)
);
GO

CREATE TABLE lgf_analytics.cliente_similitud (
    id_similitud BIGINT IDENTITY(1,1) PRIMARY KEY,
    cod_cliente_base NVARCHAR(100) NOT NULL,
    cliente_base NVARCHAR(255) NOT NULL,
    cod_cliente_similar NVARCHAR(100) NOT NULL,
    cliente_similar NVARCHAR(255) NOT NULL,
    similitud_total DECIMAL(18,6) NULL,
    similitud_producto_color DECIMAL(18,6) NULL,
    similitud_sku_flexible DECIMAL(18,6) NULL,
    similitud_sku_terminado DECIMAL(18,6) NULL,
    similitud_empaque DECIMAL(18,6) NULL,
    compatibilidad_operativa NVARCHAR(100) NULL,
    fecha_calculo DATETIME2 DEFAULT SYSDATETIME()
);
GO

CREATE TABLE lgf_analytics.demanda_operativa_futura (
    id_demanda BIGINT IDENTITY(1,1) PRIMARY KEY,
    fecha_forecast DATE NOT NULL,
    anio_forecast INT NULL,
    semana_forecast INT NULL,
    dia_semana_forecast INT NULL,
    cod_cliente NVARCHAR(100) NOT NULL,
    cliente NVARCHAR(255) NOT NULL,
    producto NVARCHAR(100) NULL,
    variedad NVARCHAR(150) NULL,
    color NVARCHAR(100) NULL,
    grado NVARCHAR(50) NULL,
    tipo_caja NVARCHAR(50) NULL,
    tallos_x_ramo NVARCHAR(50) NULL,
    capuchon NVARCHAR(255) NULL,
    comida NVARCHAR(255) NULL,
    empaque NVARCHAR(255) NULL,
    sku_terminado NVARCHAR(800) NULL,
    sku_flexible NVARCHAR(500) NULL,
    fuente_demanda NVARCHAR(100) NULL,
    tallos_estimados DECIMAL(18,4) NULL,
    observaciones_mismo_dia INT NULL,
    observaciones_generales INT NULL,
    score_compra_terminada DECIMAL(18,4) NULL,
    recomendacion_compra NVARCHAR(100) NULL,
    cumplimiento_tallos DECIMAL(18,6) NULL,
    confianza_estimacion DECIMAL(18,4) NULL,
    version_modelo NVARCHAR(150) NULL,
    fecha_generacion DATETIME2 DEFAULT SYSDATETIME()
);
GO

CREATE TABLE lgf_analytics.inventario_futuro (
    id_inventario BIGINT IDENTITY(1,1) PRIMARY KEY,
    fecha DATE NOT NULL,
    anio INT NULL,
    semana_iso INT NULL,
    anio_semana VARCHAR(10) NULL,
    producto NVARCHAR(100) NULL,
    variedad NVARCHAR(150) NULL,
    color NVARCHAR(100) NULL,
    grado NVARCHAR(50) NULL,
    cod_finca NVARCHAR(50) NULL,
    inventario DECIMAL(18,4) NULL,
    producto_color NVARCHAR(300) NULL,
    producto_variedad_color NVARCHAR(500) NULL,
    fecha_carga DATETIME2 DEFAULT SYSDATETIME()
);
GO

CREATE TABLE lgf_analytics.cruce_forecast_inventario (
    id_cruce BIGINT IDENTITY(1,1) PRIMARY KEY,
    fecha_forecast DATE NOT NULL,
    cod_cliente NVARCHAR(100) NOT NULL,
    cliente NVARCHAR(255) NOT NULL,
    producto NVARCHAR(100) NULL,
    variedad NVARCHAR(150) NULL,
    color NVARCHAR(100) NULL,
    grado NVARCHAR(50) NULL,
    tipo_caja NVARCHAR(50) NULL,
    tallos_x_ramo NVARCHAR(50) NULL,
    capuchon NVARCHAR(255) NULL,
    comida NVARCHAR(255) NULL,
    empaque NVARCHAR(255) NULL,
    fuente_demanda NVARCHAR(100) NULL,
    tallos_estimados DECIMAL(18,4) NULL,
    inventario_total DECIMAL(18,4) NULL,
    faltante_proyectado_item DECIMAL(18,4) NULL,
    sobrante_proyectado_item DECIMAL(18,4) NULL,
    riesgo_disponibilidad NVARCHAR(100) NULL,
    tallos_prioridad_compra_cliente DECIMAL(18,4) NULL,
    prioridad_compra NVARCHAR(100) NULL,
    score_compra_terminada DECIMAL(18,4) NULL,
    confianza_estimacion DECIMAL(18,4) NULL,
    fecha_calculo DATETIME2 DEFAULT SYSDATETIME()
);
GO
