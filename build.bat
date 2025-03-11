@echo off
setlocal


SET PROJECT_NAME=partomatic

SET /P PYTEST_CHOSEN=Do you want to run pytest --cov ([Y]/N)?
IF /I "%PYTEST_CHOSEN%" NEQ "N" GOTO TEST
GOTO BUILD

:TEST
pytest --cov

SET /P PYTEST_CLEAN=Based on the pytest results, proceed with the build? ([Y]/N)?
IF /I "%PYTEST_CLEAN%" NEQ "N" GOTO BUILD

GOTO END

:BUILD
py -m pip uninstall -y %PROJECT_NAME%
del /F /Q dist\*.*

py -m build
py -m pip install -e .

:TESTLOCAL
python -c "exec(\"from partomatic import Partomatic, PartomaticConfig, AutomatablePart\nprint(PartomaticConfig().stl_folder)\")"


SET /P PYPI_UPLOAD=Based on that simple test, upload to pypi? ([Y]/N)?
IF /I "%PYPI_UPLOAD%" NEQ "N" GOTO UPLOAD

GOTO END

:UPLOAD
py -m twine upload dist/*
py -m pip uninstall -y partomatic
py -m pip install partomatic
python -c "exec(\"from partomatic import Partomatic, PartomaticConfig, AutomatablePart\nprint(PartomaticConfig().stl_folder)\")"

ECHO "REMINDER!!! Commit and push git changes!!!"

:END
endlocal
