using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using OtterWorks.AuditService.Config;
using OtterWorks.AuditService.Models;
using OtterWorks.AuditService.Services;

namespace AuditService.Tests;

public class AdminAuditReportTests
{
    private readonly Mock<IAuditRepository> _repository = new();
    private readonly Mock<IAuditArchiver> _archiver = new();
    private readonly OtterWorks.AuditService.Services.AuditService _service;

    public AdminAuditReportTests()
    {
        _service = new OtterWorks.AuditService.Services.AuditService(
            _repository.Object,
            _archiver.Object,
            Options.Create(new AwsSettings { ArchiveAfterDays = 30 }),
            new Mock<ILogger<OtterWorks.AuditService.Services.AuditService>>().Object);
    }

    private static AuditEvent Event(string userId, string action, string resourceType, DateTime timestamp, string? resourceId = null) => new()
    {
        Id = Guid.NewGuid().ToString(),
        UserId = userId,
        Action = action,
        ResourceType = resourceType,
        ResourceId = resourceId ?? Guid.NewGuid().ToString(),
        Timestamp = timestamp,
    };

    [Fact]
    public async Task RecordEventAsync_CopiesDetailsAndGeneratesUniqueIds()
    {
        var saved = new List<AuditEvent>();
        _repository.Setup(r => r.SaveEventAsync(It.IsAny<AuditEvent>()))
            .Callback<AuditEvent>(saved.Add)
            .Returns(Task.CompletedTask);
        var request = new AuditEventRequest
        {
            UserId = "admin-1",
            Action = "user.suspended",
            ResourceType = "user",
            ResourceId = "u-1",
            Details = new Dictionary<string, string> { ["reason"] = "abuse" },
        };

        var first = await _service.RecordEventAsync(request);
        var second = await _service.RecordEventAsync(request);

        Assert.NotEqual(first.Id, second.Id);
        Assert.Equal("abuse", saved[0].Details!["reason"]);
        Assert.Equal(DateTimeKind.Utc, saved[0].Timestamp.Kind);
    }

    [Fact]
    public async Task GetEventAsync_ReturnsNullWhenMissing()
    {
        _repository.Setup(r => r.GetEventAsync("missing")).ReturnsAsync((AuditEvent?)null);
        Assert.Null(await _service.GetEventAsync("missing"));
    }

    [Fact]
    public async Task QueryEventsAsync_PassesAllFiltersThrough()
    {
        var from = DateTime.UtcNow.AddDays(-1);
        var to = DateTime.UtcNow;
        var page = new AuditEventPage { Total = 7, Page = 2, PageSize = 5 };
        _repository.Setup(r => r.QueryEventsAsync("u", "login", "user", "r", from, to, 2, 5)).ReturnsAsync(page);

        var result = await _service.QueryEventsAsync("u", "login", "user", "r", from, to, 2, 5);

        Assert.Same(page, result);
    }

    [Theory]
    [InlineData("day", 1)]
    [InlineData("24h", 1)]
    [InlineData("week", 7)]
    [InlineData("7d", 7)]
    [InlineData("MONTH", 30)]
    [InlineData("quarter", 90)]
    [InlineData("year", 365)]
    [InlineData("bogus", 30)]
    public async Task GetComplianceReportAsync_MapsPeriodToDateRange(string period, int expectedDays)
    {
        DateTime capturedFrom = default, capturedTo = default;
        _repository.Setup(r => r.GetEventsByDateRangeAsync(It.IsAny<DateTime>(), It.IsAny<DateTime>()))
            .Callback<DateTime, DateTime>((f, t) => { capturedFrom = f; capturedTo = t; })
            .ReturnsAsync(new List<AuditEvent>());

        var report = await _service.GetComplianceReportAsync(period);

        Assert.Equal(period, report.Period);
        Assert.Equal(expectedDays, Math.Round((capturedTo - capturedFrom).TotalDays));
    }

    [Fact]
    public async Task GetComplianceReportAsync_EmptyRangeHasNoUsersOrSuspicion()
    {
        _repository.Setup(r => r.GetEventsByDateRangeAsync(It.IsAny<DateTime>(), It.IsAny<DateTime>()))
            .ReturnsAsync(new List<AuditEvent>());

        var report = await _service.GetComplianceReportAsync("week");

        Assert.Equal(0, report.TotalEvents);
        Assert.Equal(0, report.UniqueUsers);
        Assert.Empty(report.SuspiciousActivities);
    }

    [Fact]
    public async Task GetComplianceReportAsync_FlagsOnlyUsersAboveThreshold()
    {
        var now = DateTime.UtcNow;
        var events = new List<AuditEvent>();
        for (var i = 0; i < 101; i++) events.Add(Event("noisy", "read", "file", now));
        for (var i = 0; i < 100; i++) events.Add(Event("at-threshold", "read", "file", now));
        for (var i = 0; i < 10; i++) events.Add(Event($"quiet-{i}", "update", "document", now));
        _repository.Setup(r => r.GetEventsByDateRangeAsync(It.IsAny<DateTime>(), It.IsAny<DateTime>()))
            .ReturnsAsync(events);

        var report = await _service.GetComplianceReportAsync("day");

        var flagged = Assert.Single(report.SuspiciousActivities);
        Assert.Equal("noisy", flagged.UserId);
        Assert.Equal(101, flagged.EventCount);
        Assert.Equal(12, report.UniqueUsers);
        Assert.Equal(201, report.ActionBreakdown["read"]);
        Assert.Equal(10, report.ResourceTypeBreakdown["document"]);
    }

    [Fact]
    public async Task GetUserActivityReportAsync_ExcludesEventsOutsidePeriod()
    {
        var now = DateTime.UtcNow;
        _repository.Setup(r => r.GetAllUserEventsAsync("u1")).ReturnsAsync(new List<AuditEvent>
        {
            Event("u1", "login", "user", now.AddHours(-2)),
            Event("u1", "update", "document", now.AddDays(-3)),
            Event("u1", "delete", "file", now.AddDays(-40)),
        });

        var report = await _service.GetUserActivityReportAsync("u1", "week");

        Assert.Equal(2, report.TotalEvents);
        Assert.False(report.ActionCounts.ContainsKey("delete"));
        Assert.Equal("login", report.RecentEvents.First().Action);
        Assert.True(report.FirstActivity < report.LastActivity);
    }

    [Fact]
    public async Task GetUserActivityReportAsync_CapsRecentEventsAtTenNewestFirst()
    {
        var now = DateTime.UtcNow;
        var events = Enumerable.Range(0, 15).Select(i => Event("u1", "read", "file", now.AddMinutes(-i))).ToList();
        _repository.Setup(r => r.GetAllUserEventsAsync("u1")).ReturnsAsync(events);

        var report = await _service.GetUserActivityReportAsync("u1", "day");

        Assert.Equal(15, report.TotalEvents);
        Assert.Equal(10, report.RecentEvents.Count);
        Assert.Equal(report.RecentEvents.OrderByDescending(e => e.Timestamp).Select(e => e.Id), report.RecentEvents.Select(e => e.Id));
    }

    [Fact]
    public async Task GetUserActivityReportAsync_NoEventsHasNullActivityBounds()
    {
        _repository.Setup(r => r.GetAllUserEventsAsync("nobody")).ReturnsAsync(new List<AuditEvent>());

        var report = await _service.GetUserActivityReportAsync("nobody", "month");

        Assert.Equal(0, report.TotalEvents);
        Assert.Null(report.FirstActivity);
        Assert.Null(report.LastActivity);
    }

    [Fact]
    public async Task GetResourceHistoryAsync_MapsEveryEvent()
    {
        var now = DateTime.UtcNow;
        _repository.Setup(r => r.GetResourceHistoryAsync("doc-1")).ReturnsAsync(new List<AuditEvent>
        {
            Event("u1", "create", "document", now.AddDays(-1), "doc-1"),
            Event("u2", "share", "document", now, "doc-1"),
        });

        var history = await _service.GetResourceHistoryAsync("doc-1");

        Assert.Equal("doc-1", history.ResourceId);
        Assert.Equal(2, history.TotalEvents);
        Assert.All(history.Events, e => Assert.Equal("doc-1", e.ResourceId));
    }

    [Fact]
    public async Task ArchiveOldEventsAsync_UsesConfiguredRetention()
    {
        DateTime cutoff = default;
        _archiver.Setup(a => a.ArchiveOldEventsAsync(It.IsAny<DateTime>()))
            .Callback<DateTime>(c => cutoff = c)
            .ReturnsAsync(new ArchiveResult());

        await _service.ArchiveOldEventsAsync();

        Assert.Equal(30, Math.Round((DateTime.UtcNow - cutoff).TotalDays));
    }

    [Fact]
    public async Task ExportAsync_DelegatesToArchiver()
    {
        var from = DateTime.UtcNow.AddDays(-7);
        var to = DateTime.UtcNow;
        var expected = new ExportResult();
        _archiver.Setup(a => a.ExportAsync(from, to, "csv")).ReturnsAsync(expected);

        Assert.Same(expected, await _service.ExportAsync(from, to, "csv"));
    }
}
