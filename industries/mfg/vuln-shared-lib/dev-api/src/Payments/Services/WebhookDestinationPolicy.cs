using System.Net;
using System.Net.Sockets;

namespace Payments.Services;

public interface IWebhookHostResolver
{
    Task<IPAddress[]> Resolve(string host, CancellationToken cancellationToken);
}

public sealed class DnsWebhookHostResolver : IWebhookHostResolver
{
    public Task<IPAddress[]> Resolve(string host, CancellationToken cancellationToken) =>
        Dns.GetHostAddressesAsync(host, cancellationToken);
}

public sealed class WebhookDestinationPolicy(IWebhookHostResolver resolver)
{
    public async Task Validate(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme != "https")
            throw new InvalidDataException("HTTPS webhook destination required.");
        await Addresses(uri.DnsSafeHost, CancellationToken.None);
    }

    private async Task<IPAddress[]> Addresses(string host, CancellationToken cancellationToken)
    {
        IPAddress[] addresses;
        try
        {
            addresses = IPAddress.TryParse(host, out var literal)
                ? [literal] : await resolver.Resolve(host, cancellationToken);
        }
        catch (SocketException exception)
        {
            throw new InvalidDataException("Webhook host could not be resolved.", exception);
        }
        if (addresses.Length == 0 || addresses.Any(address => !IsPublic(address)))
            throw new InvalidDataException("Webhook destination is not public.");
        return addresses;
    }

    public static bool IsPublic(IPAddress address)
    {
        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();
        if (IPAddress.IsLoopback(address)) return false;
        var bytes = address.GetAddressBytes();
        if (address.AddressFamily == AddressFamily.InterNetwork)
            return bytes[0] != 0 && bytes[0] != 10 && bytes[0] != 127 &&
                !(bytes[0] == 100 && bytes[1] >= 64 && bytes[1] <= 127) &&
                !(bytes[0] == 169 && bytes[1] == 254) &&
                !(bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31) &&
                !(bytes[0] == 192 && bytes[1] == 168) && bytes[0] < 224;
        return address.AddressFamily == AddressFamily.InterNetworkV6 &&
            !address.Equals(IPAddress.IPv6Any) && !address.IsIPv6LinkLocal &&
            !address.IsIPv6Multicast && !address.IsIPv6SiteLocal && (bytes[0] & 0xfe) != 0xfc;
    }

    public async ValueTask<Stream> Connect(SocketsHttpConnectionContext context, CancellationToken cancellationToken)
    {
        var addresses = await Addresses(context.DnsEndPoint.Host, cancellationToken);
        var socket = new Socket(SocketType.Stream, ProtocolType.Tcp);
        try
        {
            await socket.ConnectAsync(addresses, context.DnsEndPoint.Port, cancellationToken);
            if (socket.RemoteEndPoint is not IPEndPoint remote || !IsPublic(remote.Address))
                throw new InvalidDataException("Connected webhook destination is not public.");
            return new NetworkStream(socket, ownsSocket: true);
        }
        catch
        {
            socket.Dispose();
            throw;
        }
    }
}
