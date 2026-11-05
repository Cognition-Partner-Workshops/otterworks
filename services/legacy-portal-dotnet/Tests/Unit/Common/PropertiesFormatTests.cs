using OtterWorks.LegacyPortal.Configuration;

namespace OtterWorks.LegacyPortal.Tests.Unit.Common;

public class PropertiesFormatTests
{
    [Fact]
    public void Parses_separators_comments_and_whitespace()
    {
        var values = PropertiesFormat.Parse("# comment\n! also comment\n\n  a = 1\nb:2\nc 3\nd=\n e=  spaced value  \r\n");

        values.Should().BeEquivalentTo(new Dictionary<string, string>
        {
            ["a"] = "1",
            ["b"] = "2",
            ["c"] = "3",
            ["d"] = string.Empty,
            ["e"] = "spaced value  ",
        });
    }

    [Fact]
    public void Joins_continuation_lines_and_unescapes()
    {
        var values = PropertiesFormat.Parse("multi=one \\\n    two\nesc=tab\\there \\u0041\\\\\nkey\\=with\\:sep=v\n");

        values["multi"].Should().Be("one two");
        values["esc"].Should().Be("tab\there A\\");
        values["key=with:sep"].Should().Be("v");
    }

    [Fact]
    public void First_occurrence_of_a_repeated_key_wins()
    {
        PropertiesFormat.Parse("k=first\nk=second\n")["k"].Should().Be("first");
    }
}
