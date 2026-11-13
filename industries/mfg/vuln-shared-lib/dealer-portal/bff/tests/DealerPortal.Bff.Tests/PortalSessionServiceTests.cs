using DealerPortal.Bff.Session;
using Microsoft.Extensions.Options;
using Platform.Shared.Crypto;

namespace DealerPortal.Bff.Tests;

public sealed class PortalSessionServiceTests
{
    private sealed class FixedClock(DateTimeOffset now) : TimeProvider
    {
        public DateTimeOffset Now { get; set; } = now;
        public override DateTimeOffset GetUtcNow() => Now;
    }

    private static readonly DateTimeOffset IssuedAt = DateTimeOffset.FromUnixTimeSeconds(1798761600);

    private readonly FixedClock _clock = new(IssuedAt);
    private readonly PortalSessionService _sessions;

    public PortalSessionServiceTests() =>
        _sessions = new PortalSessionService(_clock, Options.Create(new PortalOptions()), SyntheticSigning.Provider);

    [Fact]
    public void Encode_SignsTheBase64UrlPayload()
    {
        var session = _sessions.Create(StubUpstream.Email, StubUpstream.DealerId, StubUpstream.AccessToken, 3600);

        var cookie = _sessions.Encode(session);

        var parts = cookie.Split('.');
        Assert.Equal(2, parts.Length);
        Assert.Equal(TokenSigner.Sign(parts[0], SyntheticSigning.Provider), parts[1]);
        Assert.Equal(1798765200, session.ExpiresAtUnix);
    }

    [Fact]
    public void Decode_RoundTripsAValidCookie()
    {
        var session = _sessions.Create(StubUpstream.Email, StubUpstream.DealerId, StubUpstream.AccessToken, 3600);
        Assert.Equal(session, _sessions.Decode(_sessions.Encode(session)));
    }

    [Fact]
    public void Decode_RejectsExpiredSessions()
    {
        var cookie = _sessions.Encode(_sessions.Create(StubUpstream.Email, StubUpstream.DealerId, "t", 60));
        _clock.Now = IssuedAt.AddSeconds(61);
        Assert.Null(_sessions.Decode(cookie));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("no-signature")]
    [InlineData("payload.")]
    [InlineData(".signature")]
    public void Decode_RejectsMalformedCookies(string? cookie) => Assert.Null(_sessions.Decode(cookie));

    [Fact]
    public void Decode_AcceptsRetainedKeyAfterRotationAndRejectsRemovedKey()
    {
        var cookie = _sessions.Encode(_sessions.Create(StubUpstream.Email, StubUpstream.DealerId, "t", 60));
        var next = new SigningKey("vsl-synthetic-next", Enumerable.Repeat((byte)42, 32).ToArray());
        var retained = new SigningKeyRing(next, new[] { next, SyntheticSigning.Provider.CurrentKey });
        var rotated = new PortalSessionService(_clock, Options.Create(new PortalOptions()), retained);
        Assert.NotNull(rotated.Decode(cookie));
        var removed = new PortalSessionService(_clock, Options.Create(new PortalOptions()), new SigningKeyRing(next, new[] { next }));
        Assert.Null(removed.Decode(cookie));
        Assert.NotNull(removed.Decode(rotated.Encode(rotated.Create(StubUpstream.Email, StubUpstream.DealerId, "t", 60))));
    }

    [Fact]
    public void Decode_RejectsModifiedSignature()
    {
        var cookie = _sessions.Encode(_sessions.Create(StubUpstream.Email, StubUpstream.DealerId, "t", 60));
        Assert.Null(_sessions.Decode(cookie[..^1] + (cookie[^1] == 'A' ? "B" : "A")));
    }

    [Fact]
    public void Decode_RejectsAModifiedPayload()
    {
        var cookie = _sessions.Encode(_sessions.Create(StubUpstream.Email, StubUpstream.DealerId, "t", 60));
        var forged = Base64Url.Encode(System.Text.Encoding.UTF8.GetBytes("{\"sub\":\"x\",\"dealer\":\"D-2002\",\"at\":\"t\",\"exp\":1798761660}"));
        Assert.Null(_sessions.Decode(forged + cookie[cookie.IndexOf('.')..]));
    }
}
