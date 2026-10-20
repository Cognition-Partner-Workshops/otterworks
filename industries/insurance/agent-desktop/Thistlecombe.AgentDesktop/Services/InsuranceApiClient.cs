using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Threading.Tasks;
using OtterWorks.Desktop.Services;
using Thistlecombe.AgentDesktop.Models;

namespace Thistlecombe.AgentDesktop.Services
{
    /// <summary>Read-only insurance routes on the gateway: GET /policies and GET /claims.</summary>
    public class InsuranceApiClient
    {
        private readonly HttpClient _http;
        private readonly SessionState _session;

        public InsuranceApiClient(AppSettings settings, SessionState session, HttpMessageHandler? handler = null)
        {
            _session = session;
            _http = handler == null ? new HttpClient() : new HttpClient(handler);
            _http.BaseAddress = new Uri(settings.ApiBaseUrl.TrimEnd('/') + "/");
            _http.Timeout = TimeSpan.FromSeconds(30);
        }

        public Task<PolicyListResponse> GetPoliciesAsync() => GetAsync<PolicyListResponse>("policies");

        public Task<ClaimListResponse> GetClaimsAsync() => GetAsync<ClaimListResponse>("claims");

        private async Task<T> GetAsync<T>(string path) where T : new()
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, path);
            if (!string.IsNullOrEmpty(_session.AccessToken))
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _session.AccessToken);
            }

            HttpResponseMessage response;
            try
            {
                response = await _http.SendAsync(request).ConfigureAwait(false);
            }
            catch (HttpRequestException ex)
            {
                throw new ApiException(0, "Could not reach the server: " + ex.Message);
            }
            catch (TaskCanceledException)
            {
                throw new ApiException(HttpStatusCode.RequestTimeout, "The request timed out.");
            }

            using (response)
            {
                string body = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!response.IsSuccessStatusCode)
                {
                    throw new ApiException(response.StatusCode,
                        string.Format("Request failed ({0} {1}).", (int)response.StatusCode, response.ReasonPhrase));
                }

                try
                {
                    return JsonSerializer.Deserialize<T>(body, InsuranceJson.Options) ?? new T();
                }
                catch (JsonException)
                {
                    throw new ApiException(response.StatusCode, "The server returned an unexpected response.");
                }
            }
        }
    }
}
