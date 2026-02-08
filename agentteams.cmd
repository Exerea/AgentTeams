@echo off
setlocal EnableDelayedExpansion
set "SCRIPT=%~dp0scripts\at.py"

where python >nul 2>nul
if not errorlevel 1 (
  python "%SCRIPT%" %*
  exit /b !ERRORLEVEL!
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%SCRIPT%" %*
  exit /b !ERRORLEVEL!
)

echo ERROR [PATH_LAYOUT_INVALID] python runtime not found (python or py -3 required).
echo Next: Install python, then retry: agentteams init ^<git-url^>
echo Compat: .\at.cmd init ^<git-url^>
exit /b 1
