using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>In-process HTTP handler that answers by request path, recording each call.</summary>
    internal sealed class StubHttpHandler : HttpMessageHandler
    {
        private readonly Dictionary<string, Queue<Tuple<HttpStatusCode, string>>> _responses =
            new Dictionary<string, Queue<Tuple<HttpStatusCode, string>>>(StringComparer.OrdinalIgnoreCase);

        public List<string> Requests { get; } = new List<string>();

        /// <summary>Queues a response for a path; the last queued response for a path repeats.</summary>
        public StubHttpHandler On(string path, HttpStatusCode status, string json)
        {
            if (!_responses.TryGetValue(path, out Queue<Tuple<HttpStatusCode, string>> queue))
            {
                queue = new Queue<Tuple<HttpStatusCode, string>>();
                _responses[path] = queue;
            }

            queue.Enqueue(Tuple.Create(status, json));
            return this;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string path = request.RequestUri.AbsolutePath;
            const string prefix = "/api/v1";
            if (path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                path = path.Substring(prefix.Length);
            }

            lock (Requests)
            {
                Requests.Add(request.Method + " " + path);
            }

            Tuple<HttpStatusCode, string> answer;
            lock (_responses)
            {
                if (!_responses.TryGetValue(path, out Queue<Tuple<HttpStatusCode, string>> queue) || queue.Count == 0)
                {
                    throw new InvalidOperationException("No stub response for " + path);
                }

                answer = queue.Count > 1 ? queue.Dequeue() : queue.Peek();
            }

            var response = new HttpResponseMessage(answer.Item1)
            {
                Content = new StringContent(answer.Item2, Encoding.UTF8, "application/json"),
            };
            return Task.FromResult(response);
        }
    }
}
