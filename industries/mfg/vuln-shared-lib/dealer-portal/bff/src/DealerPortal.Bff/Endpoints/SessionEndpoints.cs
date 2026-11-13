using System.Net;
using DealerPortal.Bff.Session;
using DealerPortal.Bff.Upstream;

namespace DealerPortal.Bff.Endpoints;

public static class SessionEndpoints
{
    public static RouteGroupBuilder MapSessionEndpoints(this RouteGroupBuilder bff)
    {
        bff.MapPost("/session", SignIn);
        bff.MapGet("/session", (HttpRequest request, PortalSessionService sessions) =>
            sessions.Read(request) is { } session ? Results.Ok(SessionView.From(session)) : Results.Unauthorized());
        bff.MapDelete("/session", (HttpResponse response, PortalSessionService sessions) =>
        {
            sessions.Clear(response);
            return Results.NoContent();
        });
        return bff;
    }

    private static async Task<IResult> SignIn(
        SignInRequest body, DevApiClient api, PortalSessionService sessions, HttpResponse response, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(body.Email) || string.IsNullOrEmpty(body.Password))
        {
            return Results.BadRequest();
        }

        var result = await api.SignInAsync(body with { Email = body.Email.Trim() }, ct);
        if (!result.Ok)
        {
            return result.Status is HttpStatusCode.Unauthorized or HttpStatusCode.BadRequest
                ? Results.Unauthorized()
                : Results.StatusCode((int)result.Status);
        }

        var signIn = result.Value!;
        var session = sessions.Create(body.Email.Trim(), signIn.DealerId, signIn.AccessToken, signIn.ExpiresIn);
        sessions.Write(response, session);
        return Results.Ok(SessionView.From(session));
    }
}
