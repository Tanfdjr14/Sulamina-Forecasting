@echo off
title Sulamina Forecast Server
echo Starting Sulamina Forecast Application...
cd /d "%~dp0"
streamlit run app.py
