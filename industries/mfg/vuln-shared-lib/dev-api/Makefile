CONFIG ?= Release
export NUGET_PACKAGES := $(CURDIR)/.nuget/packages

.PHONY: restore build test clean
restore:
	dotnet restore DevApi.sln
build: restore
	dotnet build DevApi.sln --no-restore -c $(CONFIG)
test:
	rm -rf "$(NUGET_PACKAGES)"
	$(MAKE) build
	dotnet test DevApi.sln --no-build -c $(CONFIG)
clean:
	rm -rf .nuget src/*/bin src/*/obj tests/*/bin tests/*/obj TestResults
