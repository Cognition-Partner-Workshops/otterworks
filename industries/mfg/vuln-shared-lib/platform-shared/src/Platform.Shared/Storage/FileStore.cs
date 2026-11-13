namespace Platform.Shared.Storage;

/// <summary>Opens files beneath a storage root without letting a relative path escape it.</summary>
public static class FileStore
{
    public static FileStream Open(string root, string relativePath)
    {
        var fullPath = Resolve(root, relativePath);
        return new FileStream(fullPath, FileMode.Open, FileAccess.Read, FileShare.Read);
    }

    public static string Resolve(string root, string relativePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(relativePath);
        if (Path.IsPathRooted(relativePath))
        {
            throw new UnauthorizedAccessException($"'{relativePath}' must be relative to the storage root.");
        }

        var rootFull = Path.GetFullPath(root);
        var rootWithSeparator = Path.EndsInDirectorySeparator(rootFull) ? rootFull : rootFull + Path.DirectorySeparatorChar;
        var candidate = Path.GetFullPath(Path.Combine(rootFull, relativePath));
        if (!candidate.StartsWith(rootWithSeparator, StringComparison.Ordinal))
        {
            throw new UnauthorizedAccessException($"'{relativePath}' resolves outside the storage root.");
        }

        return candidate;
    }
}
