using Platform.Shared.Crypto;
using DealerPortal.Bff;
using DealerPortal.Bff.Endpoints;
using DealerPortal.Bff.Notices;
using DealerPortal.Bff.Session;
using DealerPortal.Bff.Upstream;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<PortalOptions>(builder.Configuration.GetSection(PortalOptions.Section));
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<ISigningKeyProvider>(services => SigningConfiguration.Load(services.GetRequiredService<IConfiguration>()));
builder.Services.AddSingleton<PortalSessionService>();
builder.Services.AddSingleton<NoticeFeedService>();
builder.Services.AddHttpClient<DevApiClient>((sp, client) =>
{
    var baseUrl = sp.GetRequiredService<IOptions<PortalOptions>>().Value.DevApiBaseUrl;
    client.BaseAddress = new Uri(baseUrl.EndsWith('/') ? baseUrl : baseUrl + "/");
    client.Timeout = TimeSpan.FromSeconds(15);
});

var app = builder.Build();
_ = app.Services.GetRequiredService<ISigningKeyProvider>();

app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));

var bff = app.MapGroup("/bff");
bff.MapSessionEndpoints();
bff.MapDealerEndpoints();
app.Map("/bff/{**rest}", () => Results.NotFound());

var options = app.Services.GetRequiredService<IOptions<PortalOptions>>().Value;
var staticRoot = Path.GetFullPath(options.StaticRoot, app.Environment.ContentRootPath);
if (Directory.Exists(staticRoot))
{
    var files = new PhysicalFileProvider(staticRoot);
    app.UseDefaultFiles(new DefaultFilesOptions { FileProvider = files });
    app.UseStaticFiles(new StaticFileOptions { FileProvider = files });
    app.MapFallbackToFile("index.html", new StaticFileOptions { FileProvider = files });
}

app.Run();

public partial class Program;
