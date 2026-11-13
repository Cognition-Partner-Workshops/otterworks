namespace Warranty.Models;

public sealed class Claim
{
    public int Id { get; set; }
    public string DealerId { get; set; } = "";
    public string Vin { get; set; } = "";
    public string Status { get; set; } = "submitted";
    public string Description { get; set; } = "";
    public DateTimeOffset SubmittedAt { get; set; }
    public List<ClaimNote> Notes { get; set; } = [];
}

public sealed class ClaimNote
{
    public int Id { get; set; }
    public int ClaimId { get; set; }
    public string Text { get; set; } = "";
    public string Author { get; set; } = "";
}

public sealed record ClaimResponse(int Id, string Vin, string Status, string Description, DateTimeOffset SubmittedAt)
{
    public static ClaimResponse From(Claim claim)
    {
        return new(claim.Id, claim.Vin, claim.Status, claim.Description, claim.SubmittedAt);
    }
}

public sealed record CreateClaimRequest(string Vin, string Description);
public sealed record ClaimStatusRequest(string Status);
public sealed record ClaimNoteRequest(string Text);
public sealed record AttachmentResponse(string Name, long Length);

public sealed class ClaimImportBatch
{
    public List<ClaimImportItem> Items { get; set; } = [];
}

public abstract class ClaimImportItem
{
    public string Vin { get; set; } = "";
    public string Description { get; set; } = "";
}

public sealed class RepairClaimItem : ClaimImportItem
{
    public string RepairCode { get; set; } = "";
}

public sealed class PartsClaimItem : ClaimImportItem
{
    public string PartNumber { get; set; } = "";
}
