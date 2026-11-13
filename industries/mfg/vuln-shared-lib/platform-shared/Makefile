# Platform.Shared: build, test and pack into the repository-local feed the consumers restore from.
FEED ?= $(CURDIR)/artifacts/feed
CONFIG ?= Release

.PHONY: restore build test pack clean

restore:
	dotnet restore Platform.Shared.sln

build: restore
	dotnet build Platform.Shared.sln --no-restore -c $(CONFIG)

test: build
	dotnet test Platform.Shared.sln --no-build -c $(CONFIG) --logger "trx;LogFileName=platform-shared.trx"

pack: build
	mkdir -p $(FEED)
	dotnet pack src/Platform.Shared/Platform.Shared.csproj --no-build -c $(CONFIG) -o $(FEED)

clean:
	rm -rf artifacts src/*/bin src/*/obj tests/*/bin tests/*/obj
