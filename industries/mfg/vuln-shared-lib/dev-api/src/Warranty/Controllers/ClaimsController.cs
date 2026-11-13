using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Warranty.Models;
using Warranty.Repositories;
using Warranty.Services;

namespace Warranty.Controllers;

[Authorize]
[ApiController]
[Route("api/warranty/claims")]
public sealed class ClaimsController(ClaimRepository repository, ClaimService service) : ControllerBase
{
    private string DealerId => User.FindFirst("dealer")!.Value;

    [HttpGet]
    public async Task<IActionResult> List(string dealerId)
    {
        if (dealerId != DealerId)
        {
            return Forbid();
        }
        return Ok((await repository.List(dealerId)).Select(ClaimResponse.From));
    }

    [HttpGet("search")]
    public async Task<IActionResult> Search(string dealerId, string status)
    {
        if (dealerId != DealerId)
        {
            return Forbid();
        }
        return Ok((await repository.Search(dealerId, status)).Select(ClaimResponse.From));
    }

    [HttpGet("{id:int}")]
    public async Task<IActionResult> Detail(int id)
    {
        var claim = await repository.Find(DealerId, id);
        return claim is null ? NotFound() : Ok(ClaimResponse.From(claim));
    }

    [HttpPost]
    public async Task<IActionResult> Create(CreateClaimRequest request, IValidator<CreateClaimRequest> validator)
    {
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
        {
            return BadRequest(validation.Errors.Select(x => x.ErrorMessage));
        }
        var claim = await service.Create(DealerId, request);
        return Created($"/api/warranty/claims/{claim.Id}", claim);
    }

    [HttpPut("{id:int}/status")]
    public async Task<IActionResult> Status(int id, ClaimStatusRequest request, IValidator<ClaimStatusRequest> validator)
    {
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
        {
            return BadRequest(validation.Errors.Select(x => x.ErrorMessage));
        }
        var claim = await service.ChangeStatus(DealerId, id, request.Status);
        return claim is null ? NotFound() : Ok(claim);
    }

    [HttpPost("{id:int}/notes")]
    public async Task<IActionResult> AddNote(int id, ClaimNoteRequest request, IValidator<ClaimNoteRequest> validator)
    {
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
        {
            return BadRequest(validation.Errors.Select(x => x.ErrorMessage));
        }
        var note = await service.AddNote(DealerId, id, User.FindFirst("sub")!.Value, request.Text);
        return note is null ? NotFound() : Created($"/api/warranty/claims/{id}/notes/{note.Id}", note);
    }
}
