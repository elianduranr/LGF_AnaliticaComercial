/* Alinea las tablas materializadas del Dash con TIPEMPAQUE ya migrado. */
SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    UPDATE op_sales.agg_client_sku_week
    SET
        tipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque)))
        END,
        subtipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'solido_por_variedad'
            WHEN N'solido por color' THEN N'solido_por_color'
            WHEN N'surtido "m"' THEN N'surtido_m'
            ELSE LOWER(LTRIM(RTRIM(tipo_empaque)))
        END,
        familia_analisis_operativa = CASE
            WHEN LOWER(LTRIM(RTRIM(tipo_empaque))) IN (N'solido por variedad', N'solido por color')
                THEN N'SOLIDOS_COLOR_CAJA'
            ELSE N'ESTRUCTURAS_MIXTAS_RECETA'
        END;

    UPDATE op_sales.result_descriptivo_mix_sku_terminado
    SET
        tipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque)))
        END,
        subtipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'solido_por_variedad'
            WHEN N'solido por color' THEN N'solido_por_color'
            WHEN N'surtido "m"' THEN N'surtido_m'
            ELSE LOWER(LTRIM(RTRIM(tipo_empaque)))
        END;

    UPDATE op_sales.result_descriptivo_mix_tipo_pedido
    SET
        tipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque)))
        END,
        subtipo_pedido_operativo = CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'solido_por_variedad'
            WHEN N'solido por color' THEN N'solido_por_color'
            WHEN N'surtido "m"' THEN N'surtido_m'
            ELSE LOWER(LTRIM(RTRIM(tipo_empaque)))
        END;

    ;WITH type_totals AS (
        SELECT
            cod_cliente,
            cliente,
            SUM(CAST(tallos_analisis AS FLOAT)) AS tallos_total,
            SUM(CASE WHEN tipo_pedido_operativo = N'SOLIDO' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_solido,
            SUM(CASE WHEN tipo_pedido_operativo = N'SURTIDO "M"' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_surtido_m,
            SUM(CASE WHEN tipo_pedido_operativo = N'RAINBOW' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_rainbow,
            SUM(CASE WHEN tipo_pedido_operativo = N'BQT' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_bqt,
            SUM(CASE WHEN tipo_pedido_operativo = N'COMBO' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_combo,
            SUM(CASE WHEN tipo_pedido_operativo = N'BOUQUET' THEN CAST(tallos_analisis AS FLOAT) ELSE 0 END) AS tallos_bouquet
        FROM op_sales.fact_sales_line
        GROUP BY cod_cliente, cliente
    )
    UPDATE profile
    SET
        share_solido = totals.tallos_solido / NULLIF(totals.tallos_total, 0),
        share_surtido = 0,
        share_surtido_m = totals.tallos_surtido_m / NULLIF(totals.tallos_total, 0),
        share_rainbow = totals.tallos_rainbow / NULLIF(totals.tallos_total, 0),
        share_bqt = totals.tallos_bqt / NULLIF(totals.tallos_total, 0),
        share_combo = totals.tallos_combo / NULLIF(totals.tallos_total, 0),
        share_bouquet = totals.tallos_bouquet / NULLIF(totals.tallos_total, 0),
        share_bulk = 0,
        share_facil_compra = (totals.tallos_solido + totals.tallos_surtido_m) / NULLIF(totals.tallos_total, 0),
        share_estructuras_mixtas = (
            totals.tallos_surtido_m + totals.tallos_rainbow + totals.tallos_bqt
            + totals.tallos_combo + totals.tallos_bouquet
        ) / NULLIF(totals.tallos_total, 0)
    FROM op_sales.result_descriptivo_perfil_cliente AS profile
    JOIN type_totals AS totals
      ON totals.cod_cliente = profile.cod_cliente
     AND totals.cliente = profile.cliente;

    DECLARE @invalidas BIGINT;
    SELECT @invalidas = SUM(invalidas)
    FROM (
        SELECT COUNT_BIG(*) AS invalidas
        FROM op_sales.agg_client_sku_week
        WHERE tipo_pedido_operativo <> CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque))) END
        UNION ALL
        SELECT COUNT_BIG(*)
        FROM op_sales.result_descriptivo_mix_sku_terminado
        WHERE tipo_pedido_operativo <> CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque))) END
        UNION ALL
        SELECT COUNT_BIG(*)
        FROM op_sales.result_descriptivo_mix_tipo_pedido
        WHERE tipo_pedido_operativo <> CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque))) END
    ) AS checks;

    IF @invalidas <> 0
        THROW 51002, 'La validacion de tablas materializadas fallo; se revierte.', 1;

    COMMIT TRANSACTION;
    SELECT @invalidas AS filas_invalidas;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
