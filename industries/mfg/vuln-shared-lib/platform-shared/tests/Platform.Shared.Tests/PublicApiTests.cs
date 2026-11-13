using System.Reflection;
using Platform.Shared.Http;

namespace Platform.Shared.Tests;

/// <summary>
/// Consumers in dev-api and the dealer portal BFF compile against this surface. A change here
/// is a breaking change for them: update PublicApi.approved.txt only together with the
/// consumer migration and a package version bump.
/// </summary>
public class PublicApiTests
{
    [Fact]
    public void PublicSurfaceMatchesTheApprovedList()
    {
        var actual = Describe(typeof(SafeHttp).Assembly);
        var approvedPath = Path.Combine(AppContext.BaseDirectory, "PublicApi.approved.txt");
        if (Environment.GetEnvironmentVariable("UPDATE_PUBLIC_API") == "1")
        {
            File.WriteAllLines(Path.Combine(SourceDirectory(), "PublicApi.approved.txt"), actual);
            return;
        }

        var approved = File.ReadAllLines(approvedPath)
            .Where(line => line.Length > 0 && !line.StartsWith('#'))
            .ToArray();

        Assert.Equal(approved, actual);
    }

    internal static string[] Describe(Assembly assembly)
    {
        const BindingFlags flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
        var lines = new List<string>();
        foreach (var type in assembly.GetExportedTypes())
        {
            foreach (var method in type.GetMethods(flags).Where(m => !m.IsSpecialName && m.DeclaringType == type))
            {
                if (type.IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute)) ||
                    method.IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute)))
                {
                    continue;
                }

                var parameters = string.Join(", ", method.GetParameters().Select(p => $"{Name(p.ParameterType)} {p.Name}"));
                var obsolete = method.IsDefined(typeof(ObsoleteAttribute)) ? "[Obsolete] " : string.Empty;
                lines.Add($"{obsolete}{type.FullName}.{method.Name}({parameters}) -> {Name(method.ReturnType)}");
            }
        }

        return lines.Where(l => !IsRecordPlumbing(l)).Order(StringComparer.Ordinal).ToArray();
    }

    private static string SourceDirectory([System.Runtime.CompilerServices.CallerFilePath] string path = "") =>
        Path.GetDirectoryName(path)!;

    private static bool IsRecordPlumbing(string line) =>
        line.StartsWith("Platform.Shared.Http.FetchResult.", StringComparison.Ordinal);

    private static string Name(Type type)
    {
        if (!type.IsGenericType)
        {
            return type.IsArray ? Name(type.GetElementType()!) + "[]" : type.Name;
        }

        var root = type.Name[..type.Name.IndexOf('`')];
        return $"{root}<{string.Join(", ", type.GetGenericArguments().Select(Name))}>";
    }
}
