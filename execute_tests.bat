@echo off

:: set path variables
set path_venv="%cd%\.venv"
set path_install=requirements.txt
set path_main=baseclass\_run_tests.py

:: If exists, activate the virtual environment
:: Else, create the virtual environment, install requirements, and activate it
if exist %path_venv% (
  call conda.bat activate %path_venv%
) else (
  echo Creating your virtual environment...
  call conda create --prefix %path_venv% python=3.10
  call conda.bat activate %path_venv%
  python -m pip install -r %path_install%
  echo Done!
)

@echo on
:: Call your python script
python %path_main%

@echo off
:: Deactivate your environment
call conda.bat deactivate

:: Hold the command window for user closure
pause
