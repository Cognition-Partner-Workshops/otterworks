using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using Thistlecombe.AgentDesktop.Services;
using Xunit;

namespace Thistlecombe.AgentDesktop.Tests
{
    public class InsuranceApiClientTests
    {
        private sealed class Handler : HttpMessageHandler
        {
            private readonly HttpStatusCode _status;
            private readonly string _body;

            public Handler(HttpStatusCode status, string body)
            {
                _status = status;
                _body = body;
            }

            public HttpRequestMessage? Seen { get; private set; }

            protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
            {
                Seen = request;
                return Task.FromResult(new HttpResponseMessage(_status)
                {
                    Content = new StringContent(_body, Encoding.UTF8, "application/json"),
                });
            }
        }

        private static SessionState SignedIn()
        {
            var session = new SessionState(false);
            session.SetSession(new AuthResponse { AccessToken = "tok-123", TokenType = "Bearer" });
            return session;
        }

        [Fact]
        public async Task Policies_is_a_bearer_get_under_the_api_base()
        {
            var handler = new Handler(HttpStatusCode.OK,
                "{\"policies\":[{\"policy_no\":\"POL-2025-0001\",\"annual_premium\":\"1800.00\"}],\"total\":1}");
            var client = new InsuranceApiClient(new AppSettings { ApiBaseUrl = "http://gw.test/api/v1" }, SignedIn(), handler);

            var result = await client.GetPoliciesAsync();

            Assert.Equal(HttpMethod.Get, handler.Seen!.Method);
            Assert.Equal("http://gw.test/api/v1/policies", handler.Seen.RequestUri!.ToString());
            Assert.Equal("Bearer tok-123", handler.Seen.Headers.Authorization!.ToString());
            Assert.Equal(1800.00m, Assert.Single(result.Policies).AnnualPremium);
        }

        [Fact]
        public async Task Claims_reads_decimal_strings_without_loss()
        {
            var handler = new Handler(HttpStatusCode.OK,
                "{\"claims\":[{\"claim_number\":\"CLM-2026-100405\",\"reserve\":\"1253.12\",\"injury\":false}],\"total\":1}");
            var client = new InsuranceApiClient(new AppSettings { ApiBaseUrl = "http://gw.test/api/v1/" }, SignedIn(), handler);

            var result = await client.GetClaimsAsync();

            Assert.Equal("http://gw.test/api/v1/claims", handler.Seen!.RequestUri!.ToString());
            Assert.Equal(1253.12m, Assert.Single(result.Claims).Reserve);
        }

        [Fact]
        public async Task Non_success_becomes_ApiException_with_status()
        {
            var handler = new Handler(HttpStatusCode.Unauthorized, "{\"error\":\"unauthorized\"}");
            var client = new InsuranceApiClient(new AppSettings(), SignedIn(), handler);

            var ex = await Assert.ThrowsAsync<ApiException>(() => client.GetClaimsAsync());
            Assert.Equal(HttpStatusCode.Unauthorized, ex.StatusCode);
        }
    }
}
