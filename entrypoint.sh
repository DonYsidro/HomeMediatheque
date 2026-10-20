#!/bin/sh
set -e

# Crée les tables manquantes (sans effet sur une base déjà remplie)
python database.py

exec "$@"
