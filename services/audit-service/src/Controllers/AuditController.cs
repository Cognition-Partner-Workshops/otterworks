using System.Security.Claims;
using OtterWorks.AuditService.Models;
using OtterWorks.AuditService.Security;
using OtterWorks.AuditService.Services;

namespace OtterWorks.AuditService.Controllers;

public static class AuditController
{
    public static void MapAuditEndpoints(this WebApplication app)
    {
        var group = app.MapGroup("/api/v1/audit").RequireAuthorization();

        group.MapPost("/events", RecordEvent)
            .WithName("RecordAuditEvent")
            .Produces<AuditEventResponse>(StatusCodes.Status201Created)
            .Produces(StatusCodes.Status403Forbidden)
            .Produces(StatusCodes.Status400BadRequest);

        group.MapGet("/events", QueryEvents)
            .WithName("QueryAuditEvents")
            .Produces<AuditEventPage>(StatusCodes.Status200OK)
            .Produces(StatusCodes.Status403Forbidden);

        group.MapGet("/events/{id}", GetEvent)
            .WithName("GetAuditEvent")
            .Produces<AuditEventResponse>(StatusCodes.Status200OK)
            .Produces(StatusCodes.Status404NotFound);

        group.MapGet("/reports/user/{userId}", GetUserActivityReport)
            .WithName("GetUserActivityReport")
            .Produces<UserActivityReport>(StatusCodes.Status200OK)
            .Produces(StatusCodes.Status403Forbidden);

        group.MapGet("/resources/{resourceId}/history", GetResourceHistory)
            .WithName("GetResourceHistory")
            .Produces<ResourceHistory>(StatusCodes.Status200OK);

        group.MapGet("/reports/compliance", GetComplianceReport)
            .RequireAuthorization(AuditAuthorization.AdminPolicy)
            .WithName("GetComplianceReport")
            .Produces<ComplianceReport>(StatusCodes.Status200OK);

        group.MapGet("/export", ExportAuditLog)
            .RequireAuthorization(AuditAuthorization.AdminPolicy)
            .WithName("ExportAuditLog")
            .Produces<ExportResult>(StatusCodes.Status200OK);

        group.MapPost("/archive", ArchiveOldEvents)
            .RequireAuthorization(AuditAuthorization.AdminPolicy)
            .WithName("ArchiveOldEvents")
            .Produces<ArchiveResult>(StatusCodes.Status200OK);
    }

    private static async Task<IResult> RecordEvent(
        AuditEventRequest request,
        ClaimsPrincipal caller,
        IAuditService auditService)
    {
        if (string.IsNullOrWhiteSpace(request.UserId))
        {
            request.UserId = AuditAuthorization.UserId(caller) ?? string.Empty;
        }

        if (string.IsNullOrWhiteSpace(request.UserId) ||
            string.IsNullOrWhiteSpace(request.Action) ||
            string.IsNullOrWhiteSpace(request.ResourceType) ||
            string.IsNullOrWhiteSpace(request.ResourceId))
        {
            return Results.BadRequest(new { error = "UserId, Action, ResourceType, and ResourceId are required." });
        }

        // Non-admins cannot write events into another user's audit trail.
        if (!AuditAuthorization.CanReadUser(caller, request.UserId))
        {
            return Forbidden();
        }

        var response = await auditService.RecordEventAsync(request);
        return Results.Created($"/api/v1/audit/events/{response.Id}", response);
    }

    private static async Task<IResult> QueryEvents(
        string? user_id,
        string? action,
        string? resource,
        string? resource_type,
        DateTime? from,
        DateTime? to,
        int? page,
        int? size,
        ClaimsPrincipal caller,
        IAuditService auditService)
    {
        var pageNumber = page ?? 1;
        var pageSize = Math.Clamp(size ?? 20, 1, 100);

        // Non-admins only ever see their own events, whatever user_id the query names.
        if (!AuditAuthorization.IsAdmin(caller))
        {
            if (user_id is not null && !AuditAuthorization.CanReadUser(caller, user_id))
            {
                return Forbidden();
            }
            user_id = AuditAuthorization.UserId(caller);
        }

        var result = await auditService.QueryEventsAsync(user_id, action, resource_type, resource, from, to, pageNumber, pageSize);
        return Results.Ok(result);
    }

    private static async Task<IResult> GetEvent(
        string id,
        ClaimsPrincipal caller,
        IAuditService auditService)
    {
        var result = await auditService.GetEventAsync(id);
        // Another user's event is reported as missing so ids cannot be enumerated.
        if (result is null || !AuditAuthorization.CanReadUser(caller, result.UserId))
        {
            return Results.NotFound(new { error = "Event not found." });
        }
        return Results.Ok(result);
    }

    private static async Task<IResult> GetUserActivityReport(
        string userId,
        string? period,
        ClaimsPrincipal caller,
        IAuditService auditService)
    {
        if (!AuditAuthorization.CanReadUser(caller, userId))
        {
            return Forbidden();
        }

        var reportPeriod = period ?? "30d";
        var report = await auditService.GetUserActivityReportAsync(userId, reportPeriod);
        return Results.Ok(report);
    }

    private static async Task<IResult> GetResourceHistory(
        string resourceId,
        ClaimsPrincipal caller,
        IAuditService auditService)
    {
        var history = await auditService.GetResourceHistoryAsync(resourceId);
        // The audit-service does not know who owns a resource, so a non-admin sees only
        // the actions they performed on it.
        if (!AuditAuthorization.IsAdmin(caller))
        {
            var callerId = AuditAuthorization.UserId(caller);
            history.Events = history.Events.Where(e => e.UserId == callerId).ToList();
            history.TotalEvents = history.Events.Count;
        }
        return Results.Ok(history);
    }

    private static async Task<IResult> GetComplianceReport(
        string? period,
        IAuditService auditService)
    {
        var reportPeriod = period ?? "30d";
        var report = await auditService.GetComplianceReportAsync(reportPeriod);
        return Results.Ok(report);
    }

    private static async Task<IResult> ExportAuditLog(
        string? format,
        DateTime? from,
        DateTime? to,
        IAuditService auditService)
    {
        var exportFormat = format ?? "json";
        var exportFrom = from ?? DateTime.UtcNow.AddDays(-30);
        var exportTo = to ?? DateTime.UtcNow;

        if (!string.Equals(exportFormat, "csv", StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(exportFormat, "json", StringComparison.OrdinalIgnoreCase))
        {
            return Results.BadRequest(new { error = "Format must be 'csv' or 'json'." });
        }

        var result = await auditService.ExportAsync(exportFrom, exportTo, exportFormat);
        return Results.Ok(result);
    }

    private static async Task<IResult> ArchiveOldEvents(
        IAuditService auditService)
    {
        var result = await auditService.ArchiveOldEventsAsync();
        return Results.Ok(result);
    }

    private static IResult Forbidden() =>
        Results.Json(new { error = "You may only access your own audit data." }, statusCode: StatusCodes.Status403Forbidden);
}
