using Warranty.Models;
using Warranty.Repositories;

namespace Warranty.Services;

public sealed class ClaimService(ClaimRepository repository, TimeProvider clock)
{
    public async Task<ClaimResponse> Create(string dealerId, CreateClaimRequest request)
    {
        var claim = await repository.Add(new Claim
        {
            DealerId = dealerId,
            Vin = request.Vin,
            Description = request.Description,
            SubmittedAt = clock.GetUtcNow()
        });
        return ClaimResponse.From(claim);
    }

    public async Task<int> Import(string dealerId, ClaimImportBatch batch)
    {
        var requests = batch.Items.Select(item => new CreateClaimRequest(item.Vin, item.Description)).ToList();
        var validator = new Validation.CreateClaimValidator();
        if (requests.Any(request => !validator.Validate(request).IsValid))
        {
            throw new InvalidDataException("Each imported claim needs a VIN and description.");
        }
        return await repository.AddBatch(requests.Select(request => new Claim
        {
            DealerId = dealerId,
            Vin = request.Vin,
            Description = request.Description,
            SubmittedAt = clock.GetUtcNow()
        }));
    }

    public async Task<ClaimResponse?> ChangeStatus(string dealerId, int id, string status)
    {
        var claim = await repository.Find(dealerId, id);
        if (claim is null)
        {
            return null;
        }
        claim.Status = status;
        await repository.Save();
        return ClaimResponse.From(claim);
    }

    public async Task<ClaimNote?> AddNote(string dealerId, int id, string author, string text)
    {
        var claim = await repository.Find(dealerId, id);
        if (claim is null)
        {
            return null;
        }
        var note = new ClaimNote { ClaimId = id, Text = text, Author = author };
        claim.Notes.Add(note);
        await repository.Save();
        return note;
    }
}
