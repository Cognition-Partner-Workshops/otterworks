using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>A snapshot of a request taken before the client disposes it.</summary>
    internal sealed class RecordedRequest
    {
        public HttpMethod Method { get; set; }

        public Uri Uri { get; set; }

        public bool HasAuthorization { get; set; }

        public string Authorization { get; set; }

        public string Body { get; set; }

        public string ContentType { get; set; }
    }

    /// <summary>
    /// In-memory handler that records every request and answers with a canned response
    /// (or throws), so the API client can be exercised without a network.
    /// </summary>
    internal sealed class FakeHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _responder;

        public FakeHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> responder)
        {
            _responder = responder;
        }

        public List<RecordedRequest> Requests { get; } = new List<RecordedRequest>();

        public static FakeHttpMessageHandler Returning(HttpStatusCode status, string body, string mediaType = "application/json")
        {
            return new FakeHttpMessageHandler(_ => new HttpResponseMessage(status)
            {
                Content = new StringContent(body, Encoding.UTF8, mediaType),
            });
        }

        public static FakeHttpMessageHandler Throwing(Exception exception)
        {
            return new FakeHttpMessageHandler(_ => throw exception);
        }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            IEnumerable<string> authValues;
            bool hasAuth = request.Headers.TryGetValues("Authorization", out authValues);
            var recorded = new RecordedRequest
            {
                Method = request.Method,
                Uri = request.RequestUri,
                HasAuthorization = hasAuth,
                Authorization = hasAuth ? string.Join(",", authValues) : null,
            };

            if (request.Content != null)
            {
                recorded.Body = await request.Content.ReadAsStringAsync().ConfigureAwait(false);
                recorded.ContentType = request.Content.Headers.ContentType?.ToString();
            }

            Requests.Add(recorded);
            return _responder(request);
        }
    }

    internal static class TestClients
    {
        public const string BaseUrl = "http://localhost:8080/api/v1";
        public const string Token = "test-access-token";

        public static OtterWorksApiClient Create(FakeHttpMessageHandler handler, string token = Token, string baseUrl = BaseUrl)
        {
            var session = new SessionState(persist: false);
            if (token != null)
            {
                session.SetSession(new AuthResponse { AccessToken = token });
            }

            return new OtterWorksApiClient(new AppSettings { ApiBaseUrl = baseUrl }, session, handler);
        }
    }
}
