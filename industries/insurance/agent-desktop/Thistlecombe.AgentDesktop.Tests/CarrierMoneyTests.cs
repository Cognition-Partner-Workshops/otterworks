using Thistlecombe.AgentDesktop.Services;
using Xunit;

namespace Thistlecombe.AgentDesktop.Tests
{
    public class CarrierMoneyTests
    {
        // Ties at the third decimal: the only place the two named modes disagree.
        [Theory]
        [InlineData("1253.125", "1253.12")] // CLM-2026-100405: 1002.50 x 1.25, golden ReserveEstimate 1253.12
        [InlineData("2876.725", "2876.72")] // CLM-2026-100406: 2501.50 x 1.15, golden ReserveEstimate 2876.72
        [InlineData("350.205", "350.20")]
        [InlineData("350.215", "350.22")]
        [InlineData("350.2051", "350.21")]
        public void Reserve_rounds_half_to_even(string raw, string expected)
        {
            Assert.Equal(decimal.Parse(expected), CarrierMoney.RoundReserve(decimal.Parse(raw)));
        }

        [Theory]
        [InlineData("1253.125", "1253.13")]
        [InlineData("1800.005", "1800.01")]
        [InlineData("1800.015", "1800.02")]
        [InlineData("2400.00", "2400.00")]
        [InlineData("-10.005", "-10.01")]
        public void Premium_rounds_half_away_from_zero_like_oracle(string raw, string expected)
        {
            Assert.Equal(decimal.Parse(expected), CarrierMoney.RoundPremium(decimal.Parse(raw)));
        }

        [Fact]
        public void Golden_reserves_come_from_half_even_not_half_up()
        {
            Assert.Equal(1253.12m, CarrierMoney.RoundReserve(1002.50m * 1.25m));
            Assert.NotEqual(1253.12m, CarrierMoney.RoundPremium(1002.50m * 1.25m));
            Assert.Equal(2876.72m, CarrierMoney.RoundReserve(2501.50m * 1.15m));
            Assert.NotEqual(2876.72m, CarrierMoney.RoundPremium(2501.50m * 1.15m));
        }

        [Theory]
        [InlineData("1253.12", "$1,253.12")]
        [InlineData("86100", "$86,100.00")]
        [InlineData("0.5", "$0.50")]
        public void Format_is_en_us_currency_at_scale_2(string amount, string expected)
        {
            Assert.Equal(expected, CarrierMoney.Format(decimal.Parse(amount)));
        }
    }
}
