using System.Net;
using System.Net.Http.Headers;
using Dapper;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Platform.Shared.Http;

namespace Dealer.Tests;

public sealed class DealerApiFactory : WebApplicationFactory<Dealer.Program>
{
    private readonly string databaseName = "dealer-" + Guid.NewGuid().ToString("N");
    private readonly SqliteConnection connection;
    public string ExportRoot { get; } = Path.Combine(AppContext.BaseDirectory, "data", Guid.NewGuid().ToString("N"));
    public TransportStub Transport { get; } = new();

    public DealerApiFactory()
    {
        connection = new SqliteConnection($"Data Source={databaseName};Mode=Memory;Cache=Shared");
        connection.Open();
        Directory.CreateDirectory(ExportRoot);
        File.WriteAllText(Path.Combine(ExportRoot, "stock.csv"), "vin,model\nVIN1001,Atlas");
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Dealer:Database"] = $"Data Source={databaseName};Mode=Memory;Cache=Shared",
            ["Dealer:ExportRoot"] = ExportRoot
        }));
        builder.ConfigureServices(services =>
            services.AddHttpClient("images").ConfigurePrimaryHttpMessageHandler(() => Transport));
    }

    public void Seed()
    {
        connection.Execute("""
            INSERT INTO Inventory VALUES ('VIN1001','D-1001','Atlas',2027,'available',3200000,'https://images.dealer.example/atlas.png',42);
            INSERT INTO Inventory VALUES ('VIN1002','D-1001','Comet',2027,'reserved',2900000,'https://images.dealer.example/comet.png',10);
            INSERT INTO Inventory VALUES ('VIN2001','D-2001','Atlas',2026,'available',3000000,'https://images.dealer.example/atlas.png',80);
            """);
        SafeHttp.UseHandler(Transport);
    }

    public long BulletinCount() => connection.ExecuteScalar<long>("SELECT COUNT(*) FROM Bulletins");

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
        {
            connection.Dispose();
            if (Directory.Exists(ExportRoot))
                Directory.Delete(ExportRoot, true);
        }
    }
}

public sealed class TransportStub : HttpMessageHandler
{
    public HttpStatusCode Status { get; set; } = HttpStatusCode.OK;
    public string BulletinBody { get; set; } = """[{"vin":"VIN1001","priceCents":3150000}]""";
    public Uri? RequestedUri { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        RequestedUri = request.RequestUri;
        var content = request.RequestUri!.Host == "bulletins.oem.example"
            ? new StringContent(BulletinBody) : new StringContent("image-content");
        content.Headers.ContentType = new MediaTypeHeaderValue(
            request.RequestUri.Host == "bulletins.oem.example" ? "application/json" : "image/png");
        return Task.FromResult(new HttpResponseMessage(Status) { Content = content, RequestMessage = request });
    }
}
