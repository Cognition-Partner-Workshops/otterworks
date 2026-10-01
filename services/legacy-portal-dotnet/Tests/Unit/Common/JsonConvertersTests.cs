using System.Text.Json;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Tests.Unit.Common;

public class JsonConvertersTests
{
    private static readonly JsonSerializerOptions Options = SpringJson.CreateOptions();

    [Theory]
    [InlineData(0.0, "0.0")]
    [InlineData(3.0, "3.0")]
    [InlineData(3.1666666666666665, "3.1666666666666665")]
    [InlineData(4.5, "4.5")]
    public void Doubles_are_written_like_java(double value, string expected)
    {
        JsonSerializer.Serialize(value, Options).Should().Be(expected);
    }

    [Fact]
    public void Instants_drop_zero_fraction_groups_like_iso_instant()
    {
        IsoInstantConverter.Format(new DateTime(2026, 10, 1, 13, 5, 13, DateTimeKind.Utc)).Should().Be("2026-10-01T13:05:13Z");
        IsoInstantConverter.Format(new DateTime(2026, 10, 1, 13, 5, 13, 120, DateTimeKind.Utc)).Should().Be("2026-10-01T13:05:13.120Z");
        IsoInstantConverter.Format(new DateTime(2026, 10, 1, 13, 5, 13, 186, 989, DateTimeKind.Utc)).Should().Be("2026-10-01T13:05:13.186989Z");
    }

    [Theory]
    [InlineData("{\"v\":4}", 4)]
    [InlineData("{\"v\":\"4\"}", 4)]
    [InlineData("{\"v\":4.7}", 4)]
    [InlineData("{\"v\":null}", 0)]
    [InlineData("{}", 0)]
    public void Ints_coerce_like_jackson(string json, int expected)
    {
        JsonSerializer.Deserialize<IntHolder>(json, Options)!.V.Should().Be(expected);
    }

    [Theory]
    [InlineData("{\"v\":true}", true)]
    [InlineData("{\"v\":\"true\"}", true)]
    [InlineData("{\"v\":null}", false)]
    [InlineData("{}", false)]
    public void Booleans_coerce_like_jackson(string json, bool expected)
    {
        JsonSerializer.Deserialize<BoolHolder>(json, Options)!.V.Should().Be(expected);
    }

    [Fact]
    public void Non_numeric_string_for_int_is_rejected()
    {
        var act = () => JsonSerializer.Deserialize<IntHolder>("{\"v\":\"abc\"}", Options);
        act.Should().Throw<JsonException>();
    }

    public sealed class IntHolder
    {
        public int V { get; set; }
    }

    public sealed class BoolHolder
    {
        public bool V { get; set; }
    }
}
