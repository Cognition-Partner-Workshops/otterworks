using OtterWorks.AuditService.Middleware;
using OtterWorks.AuditService.Models;
using OtterWorks.AuditService.Services;

namespace OtterWorks.AuditService.Controllers;

public static class AuditController
{
    internal const string CallerItemKey = "audit.caller";
    internal static readonly TimeSpan MaxExportRange = TimeSpan.FromDays(90);

    public static void MapAuditEndpoints(this WebApplication app)
    {
        var serviceToken = Environment.GetEnvironmentVariable(AuditCaller.TokenEnvVar);
        var group = app.MapGroup("/api/v1/audit");

        // Every audit route needs an identity; privileged routes are additionally
        // limited to internal services and admin/compliance users.
        group.AddEndpointFilter(async (context, next) =>
        {
            var caller = AuditCaller.Resolve(context.HttpContext, serviceToken);
            if (!caller.IsAuthenticated)
            {
                return Results.Json(new { error = "Authentication required." }, statusCode: StatusCodes.Status401Unauthorized);
            }

            context.HttpContext.Items[CallerItemKey] = caller;
            var privileged = context.HttpContext.GetEndpoint()?.Metadata.GetMetadata<PrivilegedEndpoint>() is not null;
            if (privileged && !caller.IsPrivileged)
            {
                return Results.Json(new { error = "Forbidden." }, statusCode: StatusCodes.Status403Forbidden);
            }

            return await next(context);
        });

        group.MapPost("/events", RecordEvent)
            .WithMetadata(new PrivilegedEndpoint())
            .WithName("RecordAuditEvent")
            .Produces<AuditEventResponse>(StatusCodes.Status201Created)
            .Produces(StatusCodes.Status400BadRequest);

        group.MapGet("/events", QueryEvents)
            .WithName("QueryAuditEvents")
            .Produces<AuditEventPage>(StatusCodes.Status200OK);

        group.MapGet("/events/{id}", GetEvent)
            .WithName("GetAuditEvent")
            .Produces<AuditEventResponse>(StatusCodes.Status200OK)
            .Produces(StatusCodes.Status404NotFound);

        group.MapGet("/reports/user/{userId}", GetUserActivityReport)
            .WithName("GetUserActivityReport")
            .Produces<UserActivityReport>(StatusCodes.Status200OK);

        group.MapGet("/resources/{resourceId}/history", GetResourceHistory)
            .WithMetadata(new PrivilegedEndpoint())
            .WithName("GetResourceHistory")
            .Produces<ResourceHistory>(StatusCodes.Status200OK);

        group.MapGet("/reports/compliance", GetComplianceReport)
            .WithMetadata(new PrivilegedEndpoint())
            .WithName("GetComplianceReport")
            .Produces<ComplianceReport>(StatusCodes.Status200OK);

        group.MapGet("/export", ExportAuditLog)
            .WithMetadata(new PrivilegedEndpoint())
            .WithName("ExportAuditLog")
            .Produces<ExportResult>(StatusCodes.Status200OK);

        group.MapPost("/archive", ArchiveOldEvents)
            .WithMetadata(new PrivilegedEndpoint())
            .WithName("ArchiveOldEvents")
            .Produces<ArchiveResult>(StatusCodes.Status200OK);
    }

    private static async Task<IResult> RecordEvent(
        AuditEventRequest request,
        HttpContext http,
        IAuditService auditService)
    {
        var caller = Caller(http);
        if (!caller.IsInternal)
        {
            // Only internal services record on behalf of another actor.
            request.UserId = caller.UserId ?? string.Empty;
        }

        if (string.IsNullOrWhiteSpace(request.UserId) ||
            string.IsNullOrWhiteSpace(request.Action) ||
            string.IsNullOrWhiteSpace(request.ResourceType) ||
            string.IsNullOrWhiteSpace(request.ResourceId))
        {
            return Results.BadRequest(new { error = "UserId, Action, ResourceType, and ResourceId are required." });
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
        HttpContext http,
        IAuditService auditService)
    {
        var caller = Caller(http);
        if (!caller.IsPrivileged)
        {
            user_id = caller.UserId;
        }

        var pageNumber = page ?? 1;
        var pageSize = Math.Clamp(size ?? 20, 1, 100);

        var result = await auditService.QueryEventsAsync(user_id, action, resource_type, resource, from, to, pageNumber, pageSize);
        return Results.Ok(result);
    }

    private static async Task<IResult> GetEvent(
        string id,
        HttpContext http,
        IAuditService auditService)
    {
        var caller = Caller(http);
        var result = await auditService.GetEventAsync(id);
        if (result is null || (!caller.IsPrivileged && !string.Equals(result.UserId, caller.UserId, StringComparison.Ordinal)))
        {
            return Results.NotFound(new { error = "Event not found." });
        }

        return Results.Ok(result);
    }

    private static async Task<IResult> GetUserActivityReport(
        string userId,
        string? period,
        HttpContext http,
        IAuditService auditService)
    {
        var caller = Caller(http);
        if (!caller.IsPrivileged && !string.Equals(userId, caller.UserId, StringComparison.Ordinal))
        {
            return Results.Json(new { error = "Forbidden." }, statusCode: StatusCodes.Status403Forbidden);
        }

        var reportPeriod = period ?? "30d";
        var report = await auditService.GetUserActivityReportAsync(userId, reportPeriod);
        return Results.Ok(report);
    }

    private static async Task<IResult> GetResourceHistory(
        string resourceId,
        IAuditService auditService)
    {
        var history = await auditService.GetResourceHistoryAsync(resourceId);
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

        if (exportTo < exportFrom || exportTo - exportFrom > MaxExportRange)
        {
            return Results.BadRequest(new { error = $"Export range must be between 0 and {MaxExportRange.TotalDays} days." });
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

    private static AuditCaller Caller(HttpContext http) =>
        http.Items[CallerItemKey] as AuditCaller ?? new AuditCaller(null, false, false);
}

/// <summary>Marks an audit route as limited to internal services and admin/compliance users.</summary>
public sealed class PrivilegedEndpoint
{
}
