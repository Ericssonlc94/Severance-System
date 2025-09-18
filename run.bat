@echo off
rem Ativa o ambiente virtual
call .\venv\Scripts\activate.bat

rem Executa o script Python
echo STARTING SEVERANCE SYSTEM...
timeout /t 3 /nobreak >nul
python severance_system.py

rem Desativa o ambiente virtual ao fechar o app
call .\venv\Scripts\deactivate.bat

pause

@echo on




