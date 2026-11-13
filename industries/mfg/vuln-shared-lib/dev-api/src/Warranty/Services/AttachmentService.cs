using Platform.Shared.Storage;
using Warranty.Models;

namespace Warranty.Services;

public sealed class AttachmentService(IConfiguration configuration)
{
    public string Root(int claimId)
    {
        var root = configuration["Warranty:AttachmentRoot"] ?? "data/attachments";
        return Path.Combine(root, claimId.ToString(System.Globalization.CultureInfo.InvariantCulture));
    }

    public IReadOnlyList<AttachmentResponse> List(int claimId)
    {
        var root = Root(claimId);
        if (!Directory.Exists(root))
        {
            return [];
        }
        return Directory.EnumerateFiles(root).Select(path => new FileInfo(path))
            .OrderBy(file => file.Name)
            .Select(file => new AttachmentResponse(file.Name, file.Length)).ToList();
    }

    public Stream Preview(int claimId, string name)
    {
        if (!List(claimId).Any(file => file.Name == name))
        {
            throw new FileNotFoundException();
        }
        return FileStore.Open(Root(claimId), name);
    }
}
