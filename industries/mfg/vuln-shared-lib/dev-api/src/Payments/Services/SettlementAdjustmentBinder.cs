using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using Payments.Models;

namespace Payments.Services;

public sealed class SettlementAdjustmentBinder : ISerializationBinder
{
    public Type BindToType(string? assemblyName, string typeName)
    {
        var allowed = typeof(FeeAdjustment);
        if (typeName == allowed.FullName &&
            (assemblyName == allowed.Assembly.GetName().Name || assemblyName == allowed.Assembly.FullName))
            return allowed;
        throw new JsonSerializationException("Settlement adjustment type is not allowed.");
    }

    public void BindToName(Type serializedType, out string? assemblyName, out string? typeName)
    {
        if (serializedType != typeof(FeeAdjustment))
            throw new JsonSerializationException("Settlement adjustment type is not allowed.");
        assemblyName = serializedType.Assembly.GetName().Name;
        typeName = serializedType.FullName;
    }
}
