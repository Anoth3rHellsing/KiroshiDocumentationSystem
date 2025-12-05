#!/bin/bash

# Variables: ajusta los paths según tus necesidades
INSTALLDIR="/opt/kiroshi_documentation"         # Carpeta de destino final
SRCDIR="$HOME/kiroshi_nueva_version"            # Carpeta con los archivos nuevos
REQFILE="$SRCDIR/requirements.txt"              # Archivo de requisitos pip

echo "--------- Instalador Kiroshi (bash) ---------"

# Borra todo el contenido existente en la carpeta de destino
if [ -d "$INSTALLDIR" ]; then
    echo "Borrando archivos previos en $INSTALLDIR..."
    rm -rf "$INSTALLDIR"/*
else
    mkdir -p "$INSTALLDIR"
fi

# Copia los archivos nuevos
echo "Copiando archivos nuevos desde $SRCDIR..."
cp -r "$SRCDIR"/* "$INSTALLDIR"

# Instala los requisitos de Python
if [ -f "$REQFILE" ]; then
    echo "Instalando dependencias desde $REQFILE..."
    python3 -m pip install -r "$REQFILE"
    echo "Dependencias instaladas correctamente."
else
    echo "No se encontró requirements.txt en $SRCDIR, saltando instalación de dependencias."
fi

echo "Instalación terminada. Kiroshi listo para usar."
