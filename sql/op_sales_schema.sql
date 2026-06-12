/*
Schema operativo de ventas consolidadas LGF.

Objetivo:
- Guardar lineas de venta ya procesadas por el pipeline Python.
- Permitir reemplazos controlados por semana/rango de fechas.
- Servir como fuente estable para Dash, descriptivos y consultas posteriores.

Notas:
- No guardar credenciales en este archivo.
- Ejecutar una vez en la base gaitana.
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'op_sales')
    EXEC('CREATE SCHEMA op_sales');
GO

IF OBJECT_ID('op_sales.etl_load_batch', 'U') IS NULL
BEGIN
    CREATE TABLE op_sales.etl_load_batch (
        load_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_op_sales_etl_load_batch PRIMARY KEY,
        source_name NVARCHAR(260) NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        started_at DATETIME2(0) NOT NULL CONSTRAINT DF_op_sales_load_started DEFAULT SYSUTCDATETIME(),
        finished_at DATETIME2(0) NULL,
        status VARCHAR(20) NOT NULL CONSTRAINT DF_op_sales_load_status DEFAULT 'RUNNING',
        rows_deleted BIGINT NOT NULL CONSTRAINT DF_op_sales_load_deleted DEFAULT 0,
        rows_inserted BIGINT NOT NULL CONSTRAINT DF_op_sales_load_inserted DEFAULT 0,
        tallos_confirmados DECIMAL(20,2) NULL,
        ventas_usd DECIMAL(20,4) NULL,
        message NVARCHAR(1000) NULL
    );
END;
GO

IF OBJECT_ID('op_sales.fact_sales_line', 'U') IS NULL
BEGIN
    CREATE TABLE op_sales.fact_sales_line (
        line_key CHAR(64) NOT NULL,
        load_id BIGINT NOT NULL,
        fecha DATE NOT NULL,
        anio SMALLINT NOT NULL,
        semana_iso TINYINT NOT NULL,
        anio_semana CHAR(8) NOT NULL,

        cod_cliente VARCHAR(32) NULL,
        cliente NVARCHAR(220) NULL,
        NomCompania NVARCHAR(220) NULL,
        pais NVARCHAR(120) NULL,
        ciudad NVARCHAR(120) NULL,
        cod_cliente_consolidado VARCHAR(32) NULL,
        cliente_consolidado NVARCHAR(220) NULL,

        pedido VARCHAR(80) NULL,
        invoice VARCHAR(80) NULL,
        po NVARCHAR(120) NULL,
        estado NVARCHAR(80) NULL,
        estado_canonico VARCHAR(40) NULL,
        estado_categoria VARCHAR(40) NULL,

        tipo_pedido_operativo VARCHAR(40) NULL,
        origen_tipologia_operativa VARCHAR(80) NULL,
        subtipo_pedido_operativo VARCHAR(80) NULL,
        familia_analisis_operativa VARCHAR(80) NULL,
        enfoque_analisis_operativo VARCHAR(100) NULL,
        rol_color_operativo VARCHAR(80) NULL,

        producto NVARCHAR(120) NULL,
        variedad NVARCHAR(160) NULL,
        color NVARCHAR(100) NULL,
        grado NVARCHAR(40) NULL,
        tipo_caja NVARCHAR(80) NULL,
        caja_id NVARCHAR(80) NULL,
        id_caja NVARCHAR(80) NULL,
        caja_operativa NVARCHAR(120) NULL,

        tipo_orden_empaque NVARCHAR(120) NULL,
        tipo_empaque NVARCHAR(120) NULL,
        empaque NVARCHAR(220) NULL,
        capuchon NVARCHAR(220) NULL,
        comida NVARCHAR(220) NULL,
        receta NVARCHAR(220) NULL,
        bulkbouquet NVARCHAR(120) NULL,
        codempaque NVARCHAR(120) NULL,

        tallos_x_ramo DECIMAL(18,4) NULL,
        ramos_pedidos DECIMAL(18,4) NULL,
        ramos_confirmados DECIMAL(18,4) NULL,
        ramos_x_caja DECIMAL(18,4) NULL,
        ramos_x_caja_detalle DECIMAL(18,4) NULL,
        fulles DECIMAL(18,4) NULL,
        piezas DECIMAL(18,4) NULL,
        equivalencia DECIMAL(18,4) NULL,

        tallos_total DECIMAL(20,4) NULL,
        tallos_pedidos DECIMAL(20,4) NULL,
        tallos_analisis DECIMAL(20,4) NULL,
        tallos_confirmados DECIMAL(20,4) NULL,
        faltante_tallos DECIMAL(20,4) NULL,

        valor_unitario_original DECIMAL(20,6) NULL,
        valor_total_original DECIMAL(20,4) NULL,
        ventas_usd DECIMAL(20,4) NULL,
        moneda_original VARCHAR(20) NULL,
        usd_eur DECIMAL(18,8) NULL,
        usd_gbp DECIMAL(18,8) NULL,

        sku_terminado NVARCHAR(500) NULL,
        sku_flexible NVARCHAR(500) NULL,
        producto_color NVARCHAR(300) NULL,
        producto_variedad_color NVARCHAR(500) NULL,
        estructura_pedido NVARCHAR(500) NULL,
        empaque_operativo NVARCHAR(600) NULL,
        llave_analisis_operativo NVARCHAR(700) NULL,
        color_componente_key NVARCHAR(700) NULL,
        receta_estructura_key NVARCHAR(700) NULL,
        receta_programa_key NVARCHAR(700) NULL,
        receta_programa_tamano_key NVARCHAR(760) NULL,
        sku_operativo NVARCHAR(760) NULL,
        sku_composicion NVARCHAR(900) NULL,
        instancia_pedido_operativo NVARCHAR(900) NULL,

        tallos_componente_caja DECIMAL(20,4) NULL,
        tallos_programa_caja DECIMAL(20,4) NULL,
        tallos_componentes_caja DECIMAL(20,4) NULL,
        ramos_programa_caja_inferidos DECIMAL(20,4) NULL,
        tallos_programa_ramo DECIMAL(20,4) NULL,

        vendedor NVARCHAR(160) NULL,
        finca NVARCHAR(160) NULL,
        abrev_finca NVARCHAR(80) NULL,
        agencia_carga NVARCHAR(160) NULL,
        guia_master NVARCHAR(120) NULL,
        serial NVARCHAR(120) NULL,
        archivo_origen NVARCHAR(260) NULL,
        source_pull_date DATETIME2(0) NULL,
        inserted_at DATETIME2(0) NOT NULL CONSTRAINT DF_op_sales_line_inserted DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_op_sales_fact_sales_line PRIMARY KEY CLUSTERED (fecha, line_key),
        CONSTRAINT UQ_op_sales_fact_sales_line_key UNIQUE (line_key),
        CONSTRAINT FK_op_sales_fact_sales_line_load FOREIGN KEY (load_id)
            REFERENCES op_sales.etl_load_batch(load_id)
    );
END;
GO

IF OBJECT_ID('op_sales.fact_sales_line', 'U') IS NOT NULL
BEGIN
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN cliente NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN NomCompania NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN pais NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN ciudad NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN cliente_consolidado NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN po NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN estado NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN subtipo_pedido_operativo VARCHAR(160) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN producto NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN variedad NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN color NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN tipo_caja NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN caja_id NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN id_caja NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN caja_operativa NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN tipo_orden_empaque NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN tipo_empaque NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN empaque NVARCHAR(700) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN capuchon NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN comida NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN receta NVARCHAR(700) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN bulkbouquet NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN codempaque NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN vendedor NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN finca NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN abrev_finca NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN agencia_carga NVARCHAR(500) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN guia_master NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN serial NVARCHAR(250) NULL;
    ALTER TABLE op_sales.fact_sales_line ALTER COLUMN archivo_origen NVARCHAR(500) NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('op_sales.fact_sales_line') AND name = 'IX_op_sales_line_cliente_semana')
    CREATE INDEX IX_op_sales_line_cliente_semana
    ON op_sales.fact_sales_line (cod_cliente, anio, semana_iso)
    INCLUDE (cliente, producto, color, tipo_pedido_operativo, sku_operativo, tallos_confirmados, tallos_analisis, ventas_usd);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('op_sales.fact_sales_line') AND name = 'IX_op_sales_line_sku_semana')
    CREATE INDEX IX_op_sales_line_sku_semana
    ON op_sales.fact_sales_line (sku_operativo, anio, semana_iso)
    INCLUDE (cod_cliente, tipo_pedido_operativo, producto, color, variedad, tipo_caja, tallos_x_ramo, tallos_confirmados, ventas_usd);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('op_sales.fact_sales_line') AND name = 'IX_op_sales_line_producto_semana')
    CREATE INDEX IX_op_sales_line_producto_semana
    ON op_sales.fact_sales_line (producto, anio, semana_iso)
    INCLUDE (cod_cliente, pais, color, tallos_confirmados, ventas_usd);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('op_sales.fact_sales_line') AND name = 'IX_op_sales_line_pedido')
    CREATE INDEX IX_op_sales_line_pedido
    ON op_sales.fact_sales_line (pedido, caja_operativa, cod_cliente)
    INCLUDE (fecha, tipo_pedido_operativo, sku_operativo, producto, color, tallos_confirmados);
GO

CREATE OR ALTER VIEW op_sales.vw_sales_dashboard_week_client_product AS
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
    SUM(COALESCE(tallos_confirmados, 0)) AS tallos_confirmados,
    SUM(COALESCE(ventas_usd, 0)) AS ventas_usd,
    SUM(COALESCE(valor_total_original, 0)) AS valor_total_original,
    COUNT(DISTINCT pedido) AS pedidos,
    COUNT(DISTINCT caja_operativa) AS cajas_ids,
    CAST(SUM(COALESCE(ventas_usd, 0)) / NULLIF(SUM(COALESCE(tallos_confirmados, 0)), 0) AS DECIMAL(18,6)) AS precio_usd_tallo
FROM op_sales.fact_sales_line
GROUP BY anio, semana_iso, anio_semana, cod_cliente, producto;
GO

CREATE OR ALTER VIEW op_sales.vw_visualizador_cliente_sku_semana AS
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
    variedad,
    color,
    MAX(tipo_caja) AS tipo_caja,
    MAX(tallos_x_ramo) AS tallos_x_ramo,
    MAX(capuchon) AS capuchon,
    MAX(comida) AS comida,
    MAX(empaque) AS empaque,
    MAX(receta) AS receta,
    MAX(sku_composicion) AS sku_composicion,
    SUM(COALESCE(tallos_confirmados, 0)) AS tallos_confirmados,
    SUM(COALESCE(tallos_analisis, 0)) AS tallos_pedidos,
    SUM(COALESCE(ventas_usd, 0)) AS ventas_usd,
    COUNT(DISTINCT pedido) AS pedidos,
    COUNT(DISTINCT caja_operativa) AS cajas,
    CAST(SUM(COALESCE(ventas_usd, 0)) / NULLIF(SUM(COALESCE(tallos_confirmados, 0)), 0) AS DECIMAL(18,6)) AS precio_usd_tallo,
    CAST(SUM(COALESCE(tallos_confirmados, 0)) / NULLIF(SUM(COALESCE(tallos_analisis, 0)), 0) AS DECIMAL(18,6)) AS cumplimiento
FROM op_sales.fact_sales_line
GROUP BY anio, semana_iso, anio_semana, cod_cliente, tipo_pedido_operativo, sku_operativo, producto, variedad, color;
GO
