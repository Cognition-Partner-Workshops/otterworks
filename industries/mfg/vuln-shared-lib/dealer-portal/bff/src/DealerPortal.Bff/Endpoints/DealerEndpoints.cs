using DealerPortal.Bff.Notices;
using DealerPortal.Bff.Session;
using DealerPortal.Bff.Upstream;

namespace DealerPortal.Bff.Endpoints;

public static class DealerEndpoints
{
    public static RouteGroupBuilder MapDealerEndpoints(this RouteGroupBuilder bff)
    {
        var dealer = bff.MapGroup("").AddEndpointFilter<SessionFilter>();

        dealer.MapGet("/inventory", async (HttpContext ctx, DevApiClient api, CancellationToken ct) =>
        {
            var session = SessionFilter.Current(ctx);
            return Respond(ctx, await api.InventoryAsync(session.AccessToken, session.DealerId, ct));
        });

        dealer.MapGet("/inventory/{vin}", async (string vin, HttpContext ctx, DevApiClient api, CancellationToken ct) =>
        {
            var session = SessionFilter.Current(ctx);
            var result = await api.InventoryAsync(session.AccessToken, session.DealerId, ct);
            if (!result.Ok)
            {
                return Respond(ctx, result);
            }

            var vehicle = result.Value!.Find(v => string.Equals(v.Vin, vin, StringComparison.OrdinalIgnoreCase));
            return vehicle is null ? Results.NotFound() : Results.Ok(vehicle);
        });

        dealer.MapGet("/claims", async (HttpContext ctx, DevApiClient api, CancellationToken ct) =>
        {
            var session = SessionFilter.Current(ctx);
            return Respond(ctx, await api.ClaimsAsync(session.AccessToken, session.DealerId, ct));
        });

        dealer.MapPost("/claims", async (NewWarrantyClaim body, HttpContext ctx, DevApiClient api, CancellationToken ct) =>
        {
            if (string.IsNullOrWhiteSpace(body.Vin) || string.IsNullOrWhiteSpace(body.Description))
            {
                return Results.BadRequest();
            }

            var session = SessionFilter.Current(ctx);
            var result = await api.SubmitClaimAsync(session.AccessToken, body, ct);
            return result.Ok ? Results.Created($"/bff/claims/{result.Value!.Id}", result.Value) : Respond(ctx, result);
        });

        dealer.MapGet("/notices", async (NoticeFeedService feed) =>
            await feed.GetNoticesAsync() is { } notices ? Results.Ok(notices) : Results.StatusCode(StatusCodes.Status502BadGateway));

        return bff;
    }

    private static IResult Respond<T>(HttpContext ctx, UpstreamResult<T> result)
    {
        if (result.Ok)
        {
            return Results.Ok(result.Value);
        }

        if (result.Status == System.Net.HttpStatusCode.Unauthorized)
        {
            ctx.RequestServices.GetRequiredService<PortalSessionService>().Clear(ctx.Response);
        }

        return Results.StatusCode((int)result.Status);
    }
}
