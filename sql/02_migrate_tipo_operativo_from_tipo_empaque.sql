/*
Migra tipo operativo usando exclusivamente op_sales.fact_sales_line.tipo_empaque.

Regla:
- solido por variedad / solido por color -> SOLIDO
- cualquier otro valor conserva el texto del sistema en mayusculas

La tabla de respaldo permite restaurar las columnas modificadas por line_key.
La transaccion solo confirma si todas las filas quedan alineadas con TIPEMPAQUE.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'op_sales.bak_fact_sales_line_tipo_operativo_20260721_c906beb', N'U') IS NULL
    BEGIN
        SELECT
            line_key,
            tipo_pedido_operativo,
            origen_tipologia_operativa,
            subtipo_pedido_operativo,
            familia_analisis_operativa,
            enfoque_analisis_operativo,
            rol_color_operativo
        INTO op_sales.bak_fact_sales_line_tipo_operativo_20260721_c906beb
        FROM op_sales.fact_sales_line;

        CREATE UNIQUE CLUSTERED INDEX IX_bak_tipo_operativo_line_key
            ON op_sales.bak_fact_sales_line_tipo_operativo_20260721_c906beb(line_key);
    END;

    UPDATE target
    SET
        tipo_pedido_operativo = expected.tipo_operativo,
        origen_tipologia_operativa = N'tipo_empaque_sistema',
        subtipo_pedido_operativo = expected.subtipo_operativo,
        familia_analisis_operativa = CASE
            WHEN expected.tipo_operativo = N'SOLIDO' THEN N'SOLIDOS_COLOR_CAJA'
            ELSE N'ESTRUCTURAS_MIXTAS_RECETA'
        END,
        enfoque_analisis_operativo = CASE expected.tipo_operativo
            WHEN N'SOLIDO' THEN N'SKU_SOLIDO_COLOR_CAJA'
            WHEN N'SURTIDO "M"' THEN N'ESTRUCTURA_MEZCLA_COLOR_COMPONENTE'
            WHEN N'RAINBOW' THEN N'RECETA_RAINBOW_COLOR_COMPONENTE'
            WHEN N'BQT' THEN N'RECETA_BQT_ESTRUCTURA'
            WHEN N'BOUQUET' THEN N'RECETA_BOUQUET_ESTRUCTURA'
            WHEN N'COMBO' THEN N'COMBO_ESTRUCTURA_CAJA'
            ELSE N'REVISION_OPERATIVA'
        END,
        rol_color_operativo = CASE
            WHEN expected.tipo_operativo = N'SOLIDO' THEN N'COLOR_DEFINITORIO_SKU'
            ELSE N'COLOR_COMPONENTE_ESTRUCTURA'
        END
    FROM op_sales.fact_sales_line AS target
    CROSS APPLY (
        SELECT
            CASE LOWER(LTRIM(RTRIM(target.tipo_empaque)))
                WHEN N'solido por variedad' THEN N'SOLIDO'
                WHEN N'solido por color' THEN N'SOLIDO'
                ELSE UPPER(LTRIM(RTRIM(target.tipo_empaque)))
            END AS tipo_operativo,
            CASE LOWER(LTRIM(RTRIM(target.tipo_empaque)))
                WHEN N'solido por variedad' THEN N'solido_por_variedad'
                WHEN N'solido por color' THEN N'solido_por_color'
                WHEN N'surtido "m"' THEN N'surtido_m'
                WHEN N'bouquet' THEN N'bouquet'
                WHEN N'combo' THEN N'combo'
                WHEN N'rainbow' THEN N'rainbow'
                WHEN N'bqt' THEN N'bqt'
                ELSE LOWER(LTRIM(RTRIM(target.tipo_empaque)))
            END AS subtipo_operativo
    ) AS expected;

    DECLARE @filas_actualizadas BIGINT = @@ROWCOUNT;
    DECLARE @filas_invalidas BIGINT;

    SELECT @filas_invalidas = COUNT_BIG(*)
    FROM op_sales.fact_sales_line
    WHERE tipo_empaque IS NULL
       OR tipo_pedido_operativo <> CASE LOWER(LTRIM(RTRIM(tipo_empaque)))
            WHEN N'solido por variedad' THEN N'SOLIDO'
            WHEN N'solido por color' THEN N'SOLIDO'
            ELSE UPPER(LTRIM(RTRIM(tipo_empaque)))
          END
       OR origen_tipologia_operativa <> N'tipo_empaque_sistema';

    IF @filas_invalidas <> 0
        THROW 51001, 'La validacion de tipo operativo fallo; se revierte la transaccion.', 1;

    COMMIT TRANSACTION;

    SELECT
        @filas_actualizadas AS filas_actualizadas,
        @filas_invalidas AS filas_invalidas,
        N'op_sales.bak_fact_sales_line_tipo_operativo_20260721_c906beb' AS tabla_respaldo;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
