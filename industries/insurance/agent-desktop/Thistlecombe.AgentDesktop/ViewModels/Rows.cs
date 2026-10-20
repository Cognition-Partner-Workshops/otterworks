using System.Collections.Generic;
using System.Globalization;
using Thistlecombe.AgentDesktop.Models;
using Thistlecombe.AgentDesktop.Services;

namespace Thistlecombe.AgentDesktop.ViewModels
{
    public static class Labels
    {
        private static readonly Dictionary<string, string> Causes = new Dictionary<string, string>
        {
            ["COLL"] = "Collision",
            ["COMP"] = "Comprehensive",
            ["FIRE"] = "Fire",
            ["GLAS"] = "Glass",
            ["LIAB"] = "Liability",
            ["THFT"] = "Theft",
            ["TOWG"] = "Towing",
            ["WATR"] = "Water",
            ["WIND"] = "Wind",
        };

        /// <summary>IN_FORCE -> "In force", DECLINE_NOT_IN_FORCE -> "Decline not in force".</summary>
        public static string Status(string? code)
        {
            if (string.IsNullOrEmpty(code))
            {
                return string.Empty;
            }

            string words = code.Replace('_', ' ').ToLower(CultureInfo.InvariantCulture);
            return char.ToUpper(words[0], CultureInfo.InvariantCulture) + words.Substring(1);
        }

        public static string Cause(string? code)
        {
            if (string.IsNullOrEmpty(code))
            {
                return string.Empty;
            }

            return Causes.TryGetValue(code, out string? label) ? code + " · " + label : code;
        }
    }

    public class PolicyRow
    {
        public PolicyRow(Policy policy)
        {
            PolicyNo = policy.PolicyNo;
            Product = policy.ProductName;
            Holder = policy.HolderName;
            Premium = CarrierMoney.RoundPremium(policy.AnnualPremium);
            Status = policy.Status;
        }

        public string? PolicyNo { get; }
        public string? Product { get; }
        public string? Holder { get; }
        public decimal Premium { get; }
        public string PremiumText => CarrierMoney.Format(Premium);
        public string? Status { get; }
        public string StatusText => Labels.Status(Status);
    }

    public class ClaimRow
    {
        public ClaimRow(Claim claim)
        {
            ClaimNumber = claim.ClaimNumber;
            PolicyNumber = claim.PolicyNumber;
            LossDate = claim.LossDate;
            CauseCode = claim.CauseCode;
            Reserve = CarrierMoney.RoundReserve(claim.Reserve);
            Status = claim.Status;
        }

        public string? ClaimNumber { get; }
        public string? PolicyNumber { get; }
        public string? LossDate { get; }
        public string? CauseCode { get; }
        public string CauseText => Labels.Cause(CauseCode);
        public decimal Reserve { get; }
        public string ReserveText => CarrierMoney.Format(Reserve);
        public string? Status { get; }
        public string StatusText => Labels.Status(Status);
    }
}
