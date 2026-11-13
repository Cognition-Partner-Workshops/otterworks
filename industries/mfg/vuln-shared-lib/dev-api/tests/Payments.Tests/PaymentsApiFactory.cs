using System.Net;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Configuration;
using Payments.Models;
using Payments.Repositories;
using Payments.Services;
using Platform.Shared.Http;

namespace Payments.Tests;

public sealed class PaymentsApiFactory : WebApplicationFactory<Payments.Program>
{
    public string? ProcessorSecret { get; set; }
    public IPAddress[] WebhookAddresses { get; set; } = [IPAddress.Parse("93.184.216.34")];
    private readonly SqliteConnection connection = new("Data Source=:memory:");
    public string RemittanceUrl { get; set; } = "https://processor.example/remittance.json";
    public PaymentTransport Transport { get; } = new();

    public PaymentsApiFactory()
    {
        connection.Open();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, config) =>
        {
            config.AddInMemoryCollection(TestConfiguration.SyntheticSigning.Settings);
            config.AddInMemoryCollection(new Dictionary<string, string?> { ["Payments:Processor:RemittanceUrl"] = RemittanceUrl });
            if (ProcessorSecret is not null)
                config.AddInMemoryCollection(new Dictionary<string, string?> { ["Payments:Processor:ApiSecret"] = ProcessorSecret });
        });
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<DbContextOptions<PaymentsContext>>();
            services.RemoveAll<IWebhookHostResolver>();
            services.AddSingleton<IWebhookHostResolver>(new StubWebhookResolver(this));
            services.AddDbContext<PaymentsContext>(options => options.UseSqlite(connection));
            services.AddHttpClient("webhooks").ConfigurePrimaryHttpMessageHandler(() => Transport);
        });
    }

    public void Seed()
    {
        using var scope = Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<PaymentsContext>();
        context.Settlements.AddRange(
            new Settlement { Id = 1, DealerId = "D-1001", Reference = "ST-1001", AmountCents = 10000 },
            new Settlement { Id = 2, DealerId = "D-2001", Reference = "ST-2001", AmountCents = 5000 });
        context.Refunds.Add(new Refund { Id = 1, SettlementId = 1, DealerId = "D-1001", AmountCents = 1000, Reason = "Parts return" });
        context.Refunds.Add(new Refund { Id = 2, SettlementId = 2, DealerId = "D-2001", AmountCents = 100, Reason = "Other return" });
        context.SaveChanges();
        SafeHttp.UseHandler(Transport);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
        {
            connection.Dispose();
        }
    }
}

public sealed class StubWebhookResolver(PaymentsApiFactory factory) : IWebhookHostResolver
{
    public Task<IPAddress[]> Resolve(string host, CancellationToken cancellationToken) =>
        Task.FromResult(factory.WebhookAddresses);
}

public sealed class PaymentTransport : HttpMessageHandler
{
    public HttpStatusCode Status { get; set; } = HttpStatusCode.OK;
    public string Statement { get; set; } = """[{"reference":"REM-1001","amountCents":12000}]""";
    public string? Signature { get; private set; }
    public string? Body { get; private set; }
    public Uri? RedirectTo { get; set; }
    public List<Uri> Requests { get; } = new();
    public Uri? Destination { get; private set; }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Destination = request.RequestUri;
        Requests.Add(request.RequestUri!);
        if (RedirectTo is not null) return new HttpResponseMessage(HttpStatusCode.Found) { Headers = { Location = RedirectTo } };
        if (request.Method == HttpMethod.Post)
        {
            Signature = request.Headers.GetValues("X-Payments-Signature").Single();
            Body = await request.Content!.ReadAsStringAsync(cancellationToken);
        }
        return new HttpResponseMessage(Status)
        {
            RequestMessage = request,
            Content = new StringContent(Statement)
        };
    }
}
