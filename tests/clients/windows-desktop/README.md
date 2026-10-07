# Windows desktop client characterization tests

UI-driven tests that pin the behavior of `clients/windows-desktop` against an in-memory stub of
the gateway endpoints it calls (`POST /auth/register`, `POST /auth/login`, `GET /documents`,
`POST /documents`, `GET /files`). The same tests run unchanged against the .NET Framework 4.8
build and the .NET 8 build.

- `gateway_stub.py` — the stub (also runnable standalone: `python gateway_stub.py --port 8080`).
- `desktop_driver.py` — drives the WPF window through Windows UI Automation.
- `test_desktop_client.py` — register → empty list → create → log out → log back in, error
  messages, DPAPI session persistence, and a cross-build session check.

They need an interactive Windows desktop session (not a service account / headless runner).

```powershell
pip install -r tests/clients/windows-desktop/requirements.txt
dotnet build clients/windows-desktop/OtterWorks.Desktop.sln -c Release

$env:OTTERWORKS_DESKTOP_EXE = "clients/windows-desktop/OtterWorks.Desktop/bin/Release/net8.0-windows/OtterWorks.Desktop.exe"
# optional: another build of the client, for the cross-build DPAPI session check
# $env:OTTERWORKS_DESKTOP_PEER_EXE = "C:/path/to/other/OtterWorks.Desktop.exe"
# optional: where to write the five flow screenshots and per-test observations (JSON)
# $env:OTTERWORKS_SCREENSHOT_DIR = "out/screenshots"; $env:OTTERWORKS_RESULTS_DIR = "out/results"
python -m pytest tests/clients/windows-desktop -v
```

The tests replace `%APPDATA%\OtterWorks\session.dat` while they run and restore it afterwards.
