# ASP.NET 9 port of services/legacy-portal (Java 11 / Spring Boot 2.7). Runs on 8098 so it can sit
# alongside the Java service (8095) during the migration.
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS builder

WORKDIR /src
COPY global.json LegacyPortal.csproj ./
RUN dotnet restore LegacyPortal.csproj

COPY . .
RUN dotnet publish LegacyPortal.csproj -c Release -o /publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:9.0

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /publish .

RUN useradd -r -u 1001 appuser
USER appuser

ENV ASPNETCORE_ENVIRONMENT=Production
EXPOSE 8098
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8098/health || exit 1

ENTRYPOINT ["dotnet", "LegacyPortal.dll"]
