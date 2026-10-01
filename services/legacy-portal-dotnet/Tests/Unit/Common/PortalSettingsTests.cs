using OtterWorks.LegacyPortal.Configuration;

namespace OtterWorks.LegacyPortal.Tests.Unit.Common;

/// <summary>Port of Java <c>PortalBrandingSettingsTest</c> plus interpolation edge cases.</summary>
public class PortalSettingsTests
{
    private readonly PortalSettings _settings =
        PortalSettings.Load(Path.Combine(AppContext.BaseDirectory, PortalSettings.FileName));

    [Fact]
    public void Banner_resolves_other_settings_keys()
    {
        _settings.BannerText.Should().Be("OtterWorks Portal (on-prem) - contact portal-support@otterworks.example");
    }

    [Fact]
    public void Support_contact_is_read_directly()
    {
        _settings.SupportContact.Should().Be("portal-support@otterworks.example");
    }

    [Fact]
    public void Classification_uses_base64_decoder_lookup()
    {
        _settings.Classification.Should().Be("INTERNAL");
        _settings.Environment.Should().Be("on-prem");
    }

    [Fact]
    public void Missing_banner_falls_back_to_default_and_missing_support_to_empty()
    {
        var settings = PortalSettings.Parse("other=1\n");

        settings.BannerText.Should().Be("OtterWorks Portal");
        settings.SupportContact.Should().BeEmpty();
        settings.Get("portal.banner").Should().BeNull();
    }

    [Theory]
    [InlineData("${script:javascript:java.lang.Runtime.getRuntime()}")]
    [InlineData("${dns:address|otterworks.example}")]
    [InlineData("${url:UTF-8:http://localhost/}")]
    [InlineData("${env:PATH}")]
    [InlineData("${sys:user.home}")]
    [InlineData("${file:UTF-8:/etc/passwd}")]
    [InlineData("${unknown.key}")]
    public void Unsupported_lookups_and_unknown_keys_stay_literal(string template)
    {
        _settings.Interpolate(template).Should().Be(template);
    }

    [Fact]
    public void Interpolate_resolves_keys_and_base64_inside_text()
    {
        _settings.Interpolate("[${portal.environment}] ${base64Decoder:SGVsbG8=} ${portal.support}")
            .Should().Be("[on-prem] Hello portal-support@otterworks.example");
    }

    [Fact]
    public void Nested_references_resolve_transitively()
    {
        var settings = PortalSettings.Parse("a=${b}!\nb=${c}-${c}\nc=x\n");

        settings.Get("a").Should().Be("x-x!");
    }

    [Fact]
    public void Self_referencing_keys_are_rejected()
    {
        var settings = PortalSettings.Parse("a=${b}\nb=${a}\n");

        var act = () => settings.Get("a");

        act.Should().Throw<InvalidOperationException>().WithMessage("*Infinite loop*");
    }

    [Fact]
    public void Invalid_base64_is_rejected()
    {
        var act = () => _settings.Interpolate("${base64Decoder:not base64!}");

        act.Should().Throw<InvalidOperationException>();
    }

    [Fact]
    public void Unterminated_reference_is_left_as_is()
    {
        _settings.Interpolate("${portal.support").Should().Be("${portal.support");
    }
}
