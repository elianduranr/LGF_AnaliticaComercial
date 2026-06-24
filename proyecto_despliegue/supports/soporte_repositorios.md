# Soporte Git y DVC

## Git

- Remoto: `https://github.com/elianduranr/LGF_AnaliticaComercial.git`
- Rama de entrega: `proyecto_despliegue_lgf`
- Carpeta entregada: `proyecto_despliegue/`

Comandos usados/preparados:

```powershell
git checkout -b proyecto_despliegue_lgf
git add proyecto_despliegue
git commit -m "Entrega 1 proyecto despliegue LGF"
git push -u origin proyecto_despliegue_lgf
```

## DVC

DVC se usa para versionar la muestra de datos, no la base cruda completa.
La base cruda completa se mantiene local y se usa para ejecutar el notebook de
EDA orientado al pronostico.

Archivo versionado:

- `datos/raw/ventas_facturadas_muestra_2021_2026.csv`

Comandos:

```powershell
cd proyecto_despliegue
dvc init --subdir
dvc add datos/raw/ventas_facturadas_muestra_2021_2026.csv
dvc remote add -d localstorage dvc_storage
dvc push
```


