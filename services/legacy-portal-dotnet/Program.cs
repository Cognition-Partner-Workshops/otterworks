using FluentValidation;
using FluentValidation.AspNetCore;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using OtterWorks.LegacyPortal.Common;
using Prometheus;
using Serilog;
using Serilog.Formatting.Compact;

const string ServiceName = "legacy-portal-dotnet";

var builder = WebApplication.CreateBuilder(args);

// 1. Structured logging
builder.Host.UseSerilog((context, services, logger) => logger
    .ReadFrom.Configuration(context.Configuration)
    .Enrich.FromLogContext()
    .Enrich.WithProperty("service", ServiceName)
    .WriteTo.Console(new CompactJsonFormatter()));

// 2-3. Configuration + bounded-context services (each context registers itself via PortalModules)
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddPortalModules(builder.Configuration);

// 5. Validation (Java: javax.validation on request DTOs)
builder.Services.AddFluentValidationAutoValidation();
builder.Services.AddValidatorsFromAssemblyContaining<Program>();

builder.Services
    .AddControllers(options =>
    {
        options.SuppressImplicitRequiredAttributeForNonNullableReferenceTypes = true;
    })
    .AddJsonOptions(options => SpringJson.Configure(options.JsonSerializerOptions))
    .ConfigureApiBehaviorOptions(options =>
    {
        // Spring answers binding/validation failures with its default error body, not ProblemDetails.
        options.SuppressMapClientErrors = true;
        options.InvalidModelStateResponseFactory = context =>
        {
            var timeProvider = context.HttpContext.RequestServices.GetRequiredService<TimeProvider>();
            return new Microsoft.AspNetCore.Mvc.ObjectResult(
                ErrorResponses.SpringError(context.HttpContext, StatusCodes.Status400BadRequest, timeProvider))
            {
                StatusCode = StatusCodes.Status400BadRequest,
            };
        };
    });

// 6. OpenAPI
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// 7. Tracing
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(ServiceName, serviceVersion: "0.1.0"))
    .WithTracing(tracing =>
    {
        tracing.AddAspNetCoreInstrumentation();
        if (!string.IsNullOrEmpty(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"]))
        {
            tracing.AddOtlpExporter();
        }
    });

// 9. Health checks
builder.Services.AddHealthChecks();

// 10. CORS (Java service sets none; origins are opt-in via Cors:AllowedOrigins)
var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? [];
builder.Services.AddCors(options => options.AddDefaultPolicy(policy =>
    policy.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

// 12. Listen address
var port = builder.Configuration.GetValue("PORT", builder.Configuration.GetValue("Server:Port", 8098));
builder.WebHost.UseUrls($"http://0.0.0.0:{port}");

var app = builder.Build();

app.UseMiddleware<SecurityHeadersMiddleware>();
app.UseSerilogRequestLogging();
app.UseMiddleware<PortalErrorMiddleware>();
app.UseStatusCodePages(context => ErrorResponses.WriteSpringErrorAsync(context.HttpContext, context.HttpContext.Response.StatusCode));

// 8. Metrics
app.UseHttpMetrics();

app.UseSwagger();
app.UseSwaggerUI();
app.UseCors();

// 11. Endpoints
app.MapControllers();
app.MapMetrics();

await app.InitializePortalSchemasAsync();
await app.RunAsync();

public partial class Program
{
}
