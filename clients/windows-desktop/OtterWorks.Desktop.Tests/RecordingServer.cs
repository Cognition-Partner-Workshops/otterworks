using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>A request the client sent, as seen on the wire.</summary>
    public sealed class RecordedRequest
    {
        public string Method { get; set; }

        public string Path { get; set; }

        public string Query { get; set; }

        public string Authorization { get; set; }

        public string ContentType { get; set; }

        public string Body { get; set; }
    }

    /// <summary>
    /// In-process HTTP endpoint that records each request and answers with a canned
    /// status and body, so the tests pin exactly what the client puts on the wire and
    /// how it reads the reply.
    /// </summary>
    public sealed class RecordingServer : IDisposable
    {
        private readonly HttpListener _listener = new HttpListener();
        private readonly CancellationTokenSource _stop = new CancellationTokenSource();
        private readonly Task _loop;

        public RecordingServer(int status, string body)
        {
            Status = status;
            ResponseBody = body;
            int port = FreePort();
            BaseUrl = "http://127.0.0.1:" + port + "/api/v1";
            _listener.Prefixes.Add("http://127.0.0.1:" + port + "/");
            _listener.Start();
            _loop = Task.Run(LoopAsync);
        }

        public string BaseUrl { get; }

        public int Status { get; set; }

        public string ResponseBody { get; set; }

        public List<RecordedRequest> Requests { get; } = new List<RecordedRequest>();

        public static int FreePort()
        {
            var probe = new TcpListener(IPAddress.Loopback, 0);
            probe.Start();
            int port = ((IPEndPoint)probe.LocalEndpoint).Port;
            probe.Stop();
            return port;
        }

        public void Dispose()
        {
            _stop.Cancel();
            _listener.Stop();
            _listener.Close();
            try
            {
                _loop.Wait(TimeSpan.FromSeconds(2));
            }
            catch (AggregateException)
            {
            }
        }

        private async Task LoopAsync()
        {
            while (!_stop.IsCancellationRequested)
            {
                HttpListenerContext ctx;
                try
                {
                    ctx = await _listener.GetContextAsync().ConfigureAwait(false);
                }
                catch (Exception) when (_stop.IsCancellationRequested)
                {
                    return;
                }
                catch (HttpListenerException)
                {
                    return;
                }
                catch (ObjectDisposedException)
                {
                    return;
                }

                string body;
                using (var reader = new StreamReader(ctx.Request.InputStream, Encoding.UTF8))
                {
                    body = reader.ReadToEnd();
                }

                lock (Requests)
                {
                    Requests.Add(new RecordedRequest
                    {
                        Method = ctx.Request.HttpMethod,
                        Path = ctx.Request.Url.AbsolutePath,
                        Query = ctx.Request.Url.Query,
                        Authorization = ctx.Request.Headers["Authorization"],
                        ContentType = ctx.Request.ContentType,
                        Body = body,
                    });
                }

                ctx.Response.StatusCode = Status;
                if (!string.IsNullOrEmpty(ResponseBody))
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(ResponseBody);
                    ctx.Response.ContentType = "application/json";
                    ctx.Response.ContentLength64 = bytes.Length;
                    ctx.Response.OutputStream.Write(bytes, 0, bytes.Length);
                }

                ctx.Response.Close();
            }
        }
    }
}
