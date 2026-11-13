# Platform.Shared: build, test and pack into the repository-local feed the consumers restore from.
FEED ?= $(CURDIR)/artifacts/feed
CONFIG ?= Release

.PHONY: restore build test pack compat consumer-compat clean

restore:
	dotnet restore Platform.Shared.sln

build: restore
	dotnet build Platform.Shared.sln --no-restore -c $(CONFIG)

test: build
	dotnet test Platform.Shared.sln --no-build -c $(CONFIG) --logger "trx;LogFileName=platform-shared.trx"

pack: build
	mkdir -p $(FEED)
	dotnet pack src/Platform.Shared/Platform.Shared.csproj --no-build -c $(CONFIG) -o $(FEED)
	bash tests/compat/pack-seeded.sh "$(FEED)"

consumer-compat: pack
	bash tests/compat/consumers.sh

compat:
	VSL_SEEDED_REF=vsl-missing-seeded-ref bash tests/compat/pack-seeded.sh "$(CURDIR)/artifacts/compat/fallback-feed"
	test -f "$(CURDIR)/artifacts/compat/fallback-feed/Platform.Shared.1.0.0.nupkg"
	./tests/compat/run.sh

clean:
	rm -rf artifacts src/*/bin src/*/obj tests/*/bin tests/*/obj
