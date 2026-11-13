using Platform.Shared.Storage;

namespace Platform.Shared.Tests;

public sealed class FileStoreTests : IDisposable
{
    private readonly string _root = Directory.CreateTempSubdirectory("vsl-filestore-").FullName;

    public FileStoreTests()
    {
        Directory.CreateDirectory(Path.Combine(_root, "claims"));
        File.WriteAllText(Path.Combine(_root, "claims", "W-1.txt"), "synthetic attachment");
    }

    [Fact]
    public void Open_ReadsAFileUnderTheRoot()
    {
        using var stream = FileStore.Open(_root, "claims/W-1.txt");
        using var reader = new StreamReader(stream);

        Assert.Equal("synthetic attachment", reader.ReadToEnd());
    }

    [Theory]
    [InlineData("../outside.txt")]
    [InlineData("claims/../../outside.txt")]
    [InlineData("/etc/hosts")]
    public void Open_RefusesPathsThatLeaveTheRoot(string relativePath)
    {
        Assert.Throws<UnauthorizedAccessException>(() => FileStore.Open(_root, relativePath));
    }

    [Fact]
    public void Resolve_RefusesASiblingDirectoryWithTheSamePrefix()
    {
        var sibling = "../" + Path.GetFileName(_root) + "-evil/x.txt";

        Assert.Throws<UnauthorizedAccessException>(() => FileStore.Resolve(_root, sibling));
    }

    public void Dispose() => Directory.Delete(_root, recursive: true);
}
