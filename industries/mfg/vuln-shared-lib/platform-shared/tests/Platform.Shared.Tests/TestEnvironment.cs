using System.Runtime.CompilerServices;

namespace Platform.Shared.Tests;

internal static class TestEnvironment
{
    [ModuleInitializer]
    internal static void SetSigningKey() =>
        Environment.SetEnvironmentVariable("PLATFORM_SIGNING_KEY", "vsl-synthetic-test-signing-key");
}
