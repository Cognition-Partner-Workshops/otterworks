using System;
using System.Globalization;

namespace Thistlecombe.AgentDesktop.Services
{
    /// <summary>
    /// Money on the agent desktop: decimal at scale 2, each column rounded the way its source system rounded.
    /// </summary>
    public static class CarrierMoney
    {
        /// <summary>
        /// Premium: <c>policies.annual_premium NUMBER(12,2)</c> is rounded by Oracle on write,
        /// half away from zero (HALF_UP in the carrier standard).
        /// </summary>
        public const MidpointRounding PremiumRounding = MidpointRounding.AwayFromZero;

        /// <summary>
        /// Reserve: <c>ReserveEstimate</c> comes from the BizTalk triage rule, which calls .NET
        /// <c>Math.Round</c>, half to even (HALF_EVEN in the carrier standard).
        /// </summary>
        public const MidpointRounding ReserveRounding = MidpointRounding.ToEven;

        public static readonly CultureInfo DisplayCulture = CultureInfo.GetCultureInfo("en-US");

        public static decimal RoundPremium(decimal amount) => Math.Round(amount, 2, PremiumRounding);

        public static decimal RoundReserve(decimal amount) => Math.Round(amount, 2, ReserveRounding);

        /// <summary>Formats an amount that is already at scale 2, so formatting never re-rounds.</summary>
        public static string Format(decimal amountAtScale2) => amountAtScale2.ToString("C2", DisplayCulture);
    }
}
