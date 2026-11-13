using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>Unkeyed SHA-256 of UTF-8 "Platform.Shared.DeviceFingerprint.v1\0" followed by
/// each UTF-8 field with a 4-byte big-endian byte length. Returns lowercase hex. Null fields are rejected.</summary>
public static class DeviceFingerprint
{
    public static string Compute(string userAgent, string deviceId)
    {
        ArgumentNullException.ThrowIfNull(userAgent);
        ArgumentNullException.ThrowIfNull(deviceId);
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        hash.AppendData(Encoding.UTF8.GetBytes("Platform.Shared.DeviceFingerprint.v1\0"));
        Span<byte> length = stackalloc byte[4];
        foreach (var field in new[] { userAgent, deviceId })
        {
            var bytes = Encoding.UTF8.GetBytes(field);
            BinaryPrimitives.WriteInt32BigEndian(length, bytes.Length);
            hash.AppendData(length);
            hash.AppendData(bytes);
        }
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }
}
