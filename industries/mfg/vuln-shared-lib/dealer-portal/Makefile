# Dealer portal: Angular 17 front end plus the .NET 8 BFF that serves it and consumes Platform.Shared.
# Run `make vsl-pack` at the repository root first so the local Platform.Shared feed exists.

# Project-local package cache: Platform.Shared is repacked under the same version, so a shared
# cache would keep compiling the previous build of the library.
NUGET_PACKAGES ?= $(CURDIR)/.nuget/packages
export NUGET_PACKAGES
NUGET_CONFIG ?= $(CURDIR)/bff/nuget.config
CONFIG ?= Release
BFF_SLN := bff/DealerPortal.Bff.sln

.PHONY: install build test web-build web-test bff-restore bff-build bff-test e2e clean

install:
	npm ci --no-audit --no-fund

web-build: install
	npm run build

web-test: install
	npm test

bff-restore:
	rm -rf $(NUGET_PACKAGES)/platform.shared
	dotnet restore $(BFF_SLN) --configfile $(NUGET_CONFIG) --force

bff-build: bff-restore
	dotnet build $(BFF_SLN) --no-restore -c $(CONFIG)

bff-test: bff-build
	dotnet test $(BFF_SLN) --no-build -c $(CONFIG) --logger "trx;LogFileName=dealer-portal-bff.trx"

build: web-build bff-build

test:
	rm -rf $(NUGET_PACKAGES)
	$(MAKE) web-test bff-test

e2e: web-build bff-build
	npx playwright install chromium
	npx playwright test

clean:
	rm -rf node_modules dist .angular coverage test-results playwright-report .nuget bff/*/*/bin bff/*/*/obj
