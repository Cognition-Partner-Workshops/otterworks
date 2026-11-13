using Platform.Shared.Crypto;

namespace DealerPortal.Bff;

public static class SigningConfiguration
{
    public static ISigningKeyProvider Load(IConfiguration configuration)
    {
        try
        {
            var section = configuration.GetSection("Platform:Signing");
            var currentId = section["CurrentKeyId"];
            var keys = section.GetSection("Keys").GetChildren().Select(entry =>
                SigningKey.FromBase64(entry["Id"]!, entry["Material"]!)).ToArray();
            if (string.IsNullOrWhiteSpace(currentId) || keys.Length == 0 ||
                keys.Select(key => key.Id).Distinct(StringComparer.Ordinal).Count() != keys.Length)
                throw new ArgumentException("A current key id and unique keys are required.");
            var current = keys.SingleOrDefault(key => key.Id == currentId)
                ?? throw new ArgumentException("The current key id must name a configured key.");
            return new SigningKeyRing(current, keys);
        }
        catch (Exception exception) when (exception is ArgumentException or FormatException or InvalidOperationException)
        {
            throw new InvalidOperationException("Platform:Signing requires a current key id and base64 keys of at least 32 bytes. Supply signing keys through external configuration.", exception);
        }
    }
}
