import pandas as pd

from fletes_dashboard import _normalize_freight_order_type
from src.lgf_operativo.cleaning import (
    classify_tipo_pedido_operativo,
    reconcile_tipo_pedido_operativo,
)


def test_tipo_operativo_usa_solo_tipo_empaque_del_sistema():
    source = pd.DataFrame(
        {
            "tipo_empaque": [
                "solido por variedad",
                "solido por color",
                'surtido "m"',
                "bouquet",
                "combo",
                "rainbow",
                "bqt",
            ],
            # Deliberately contradictory values: none may affect the result.
            "tipo_orden_empaque": ["regular"] * 7,
            "empaque": ["combo rainbow bouquet surtido"] * 7,
            "receta": ["solido bqt bulk"] * 7,
            "tipo_pedido_referencia": ["SURTIDO"] * 7,
        }
    )

    result = classify_tipo_pedido_operativo(source)

    assert result["tipo_pedido_operativo"].tolist() == [
        "SOLIDO",
        "SOLIDO",
        'SURTIDO "M"',
        "BOUQUET",
        "COMBO",
        "RAINBOW",
        "BQT",
    ]
    assert result["tipo_pedido_raw"].tolist() == source["tipo_empaque"].tolist()
    assert result["origen_tipologia_operativa"].eq("tipo_empaque_sistema").all()


def test_reconciliacion_no_infiere_desde_empaque_o_receta():
    stale = pd.DataFrame(
        {
            "tipo_pedido_operativo": ["SURTIDO", "BOUQUET"],
            "origen_tipologia_operativa": ["regla_antigua", "referencia_historica"],
            "tipo_empaque": ["bouquet", "solido por variedad"],
            "empaque": ["surtido mixto", "bouquet combo"],
            "receta": ["rainbow", "bqt"],
        }
    )

    result = reconcile_tipo_pedido_operativo(stale)

    assert result["tipo_pedido_operativo"].tolist() == ["BOUQUET", "SOLIDO"]
    assert result["origen_tipologia_operativa"].eq("tipo_empaque_sistema").all()


def test_valor_fuera_del_catalogo_no_se_expone_como_tipo_operativo():
    source = pd.DataFrame(
        {
            "tipo_empaque": ["regular muestra"],
            "empaque": ["bouquet combo"],
            "receta": ["rainbow"],
        }
    )

    result = classify_tipo_pedido_operativo(source)

    assert result.loc[0, "tipo_pedido_operativo"] == "TIPO_EMPAQUE_NO_CLASIFICADO"


def test_fletes_usa_solo_tipo_empaque_original():
    source = pd.DataFrame(
        {
            "tipo_empaque_raw": ["bqt", "solido por color", 'surtido "m"'],
            "tipo_pedido_operativo_raw": ["BOUQUET", "RAINBOW", "COMBO"],
            "tipo_orden_empaque_raw": ["combo", "bouquet", "bqt"],
            "empaque_raw": ["rainbow", "surtido", "solido"],
            "receta_raw": ["bouquet", "combo", "rainbow"],
        }
    )

    assert _normalize_freight_order_type(source).tolist() == [
        "BQT",
        "SOLIDO",
        'SURTIDO "M"',
    ]
