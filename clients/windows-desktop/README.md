# OtterWorks Desktop (Windows)

A native **Windows desktop client** for the OtterWorks platform, built with **C# on .NET 8**
(`net8.0-windows`) using **WPF** and the **MVVM** pattern. It talks to the OtterWorks REST API
through the API gateway using `HttpClient`.

> **History:** this client was originally a classic .NET Framework 4.8 project (`packages.config`,
> `app.config`, MSBuild-only). It now uses an SDK-style project on .NET 8 with `PackageReference`
> and builds with the plain `dotnet` CLI. Screens and behavior are unchanged.

## Features

- **Register** — display name, email, password → `POST /auth/register`
- **Login** — email, password → `POST /auth/login`, with a link between the two screens
- **Documents list** — `GET /documents` (Bearer token), with a friendly empty state
- **Create document** — a *New* box → `POST /documents { title }` → list refreshes
- **Files list** — `GET /files` (nice-to-have)
- **Logout** — clears the token and returns to the login screen

The JWT access token is held **in memory**. Optionally it can be persisted between runs,
encrypted with the Windows Data Protection API (**DPAPI**, per-user scope) — see
[Configuration](#configuration). Tokens are never written to disk in plaintext.

## Project layout

```
clients/windows-desktop/
├── OtterWorks.Desktop.sln
├── README.md
├── docs/screenshots/                 # verification screenshots (embedded below)
└── OtterWorks.Desktop/
    ├── OtterWorks.Desktop.csproj      # SDK-style WPF project (net8.0-windows, PackageReference)
    ├── appsettings.json               # configurable backend base URL
    ├── App.xaml(.cs)                  # DI-free composition root + navigation templates
    ├── Models/                        # Auth (camelCase) + Document/File (snake_case) DTOs
    ├── Mvvm/                          # ObservableObject, RelayCommand, converters
    ├── Services/                      # AppSettings, SessionState (DPAPI), API client
    ├── ViewModels/                    # Login / Register / Documents / Main (shell)
    └── Views/                         # WPF views for each view model
```

## Prerequisites

- **Windows 10/11 or Windows Server 2019/2022**
- To build: the **.NET 8 SDK** (8.0.x). Visual Studio 2022 (17.8+) with the
  **.NET desktop development** workload also works.
- To run: the **.NET 8 Desktop Runtime** (`Microsoft.WindowsDesktop.App` 8.0.x), which the SDK
  includes. A machine with only .NET Framework 4.8 cannot run this build; use a self-contained
  publish for those (see [Build](#build)).

## Configuration

The backend base URL is read from `OtterWorks.Desktop/appsettings.json` (copied next to the
executable on build):

```json
{
  "apiBaseUrl": "http://localhost:8080/api/v1",
  "persistTokens": false
}
```

- `apiBaseUrl` — the OtterWorks API gateway base. Default `http://localhost:8080/api/v1`
  (the app runs on the same host as the Docker Compose backend). Point this at any reachable
  gateway if the backend runs elsewhere.
- `persistTokens` — when `true`, the session is saved to
  `%APPDATA%\OtterWorks\session.dat`, DPAPI-encrypted for the current user, and restored on
  next launch.

## Running the backend

From the repository root (LocalStack emulates AWS — no cloud needed):

```bash
make infra-up && make up
# or, without make:
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build
```

Verify it is healthy:

```bash
curl http://localhost:8080/health      # -> {"status":"healthy",...}
```

## Build

```powershell
# From clients/windows-desktop
dotnet build OtterWorks.Desktop.sln -c Release
```

Packages restore automatically. Or open `OtterWorks.Desktop.sln` in Visual Studio 2022 and build.

To produce a folder that runs without a preinstalled .NET runtime:

```powershell
dotnet publish OtterWorks.Desktop/OtterWorks.Desktop.csproj -c Release -r win-x64 --self-contained
```

## Run

```powershell
.\OtterWorks.Desktop\bin\Release\net8.0-windows\OtterWorks.Desktop.exe
# or
dotnet run --project OtterWorks.Desktop -c Release
```

Or press **F5** in Visual Studio.

## End-to-end flow

1. **Register** a new user (display name, email, password ≥ 8 chars).
2. You land on the **Documents** list — empty for a new account.
3. Type a title and click **New** — the document appears in the list.
4. Click **Log out**, then **Sign in** with the same credentials — the document is still
   there, proving it was persisted by the real backend.

## Verification screenshots

Captured on Windows against the OtterWorks backend (auth-service, document-service and
api-gateway) running locally, base URL `http://localhost:8080/api/v1`.

### 1. Register a new user
![Register](docs/screenshots/01-register.png)

### 2. Documents list — empty for a new account
![Empty documents list](docs/screenshots/02-documents-empty.png)

### 3. Create a document — it appears in the list
![Document created](docs/screenshots/03-document-created.png)

### 4. Log out
![Logged out](docs/screenshots/04-logged-out.png)

### 5. Log back in — the document persists
![Document persists after re-login](docs/screenshots/05-document-persists.png)

## API contract used

Base URL: `http://localhost:8080/api/v1`. All non-auth calls send `Authorization: Bearer
<accessToken>`.

| Method & path        | Request                                             | Response (shape)                                        |
|----------------------|-----------------------------------------------------|---------------------------------------------------------|
| `POST /auth/register`| `{ displayName, email, password }`                  | `{ accessToken, refreshToken, tokenType, expiresIn, user }` (camelCase) |
| `POST /auth/login`   | `{ email, password }`                               | same as register                                        |
| `GET /documents`     | query `page`, `size`                                | `{ items:[…], total, page, size, pages }` (snake_case)  |
| `POST /documents`    | `{ title }`                                         | created document object (snake_case)                    |
| `GET /files`         | query `page`, `page_size`                           | `{ files:[…], total, page, page_size }` (snake_case)    |

Auth payloads are camelCase while document/file payloads are snake_case; each model carries
explicit `[JsonProperty]` attributes so one serializer handles both.
