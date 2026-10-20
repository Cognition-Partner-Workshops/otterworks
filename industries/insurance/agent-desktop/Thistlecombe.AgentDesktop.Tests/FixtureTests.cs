using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Thistlecombe.AgentDesktop.Models;
using Thistlecombe.AgentDesktop.Services;
using Thistlecombe.AgentDesktop.ViewModels;
using Xunit;

namespace Thistlecombe.AgentDesktop.Tests
{
    /// <summary>The stub fixtures, read the way the desktop reads them, show the source values to the cent.</summary>
    public class FixtureTests
    {
        private static T Load<T>(string name) =>
            JsonSerializer.Deserialize<T>(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures", name)),
                InsuranceJson.Options)!;

        [Theory]
        [InlineData("POL-2025-0001", "Standard Auto", "Chen Household", "$1,800.00", "In force")]
        [InlineData("POL-2025-0002", "HomeOwners Plus", "Robinson Family", "$2,400.00", "In force")]
        [InlineData("POL-2025-0003", "20-Year Term Life", "S. Gutierrez", "$1,200.00", "In force")]
        [InlineData("POL-2025-0004", "Standard Auto", "Kowalski LLC Fleet", "$9,600.00", "In force")]
        [InlineData("POL-2025-0005", "HomeOwners Plus", "Ncube Residence", "$2,000.00", "Lapsed")]
        public void Policy_rows_match_the_oltp_seed(string policy, string product, string holder, string premium, string status)
        {
            PolicyRow row = Load<PolicyListResponse>("policies.json").Policies
                .Select(p => new PolicyRow(p)).Single(r => r.PolicyNo == policy);
            Assert.Equal(product, row.Product);
            Assert.Equal(holder, row.Holder);
            Assert.Equal(premium, row.PremiumText);
            Assert.Equal(status, row.StatusText);
        }

        [Theory]
        [InlineData("CLM-2026-100400", "POL-AUTO-48100", "2026-09-02", "GLAS", "$350.20", "FAST_TRACK")]
        [InlineData("CLM-2026-100401", "POL-AUTO-48107", "2026-09-03", "GLAS", "$2,124.99", "FAST_TRACK")]
        [InlineData("CLM-2026-100402", "POL-AUTO-48114", "2026-09-05", "TOWG", "$185.50", "FAST_TRACK")]
        [InlineData("CLM-2026-100403", "POL-AUTO-48121", "2026-09-06", "COLL", "$9,295.00", "DECLINE_NOT_IN_FORCE")]
        [InlineData("CLM-2026-100404", "POL-AUTO-48128", "2026-09-08", "COLL", "$24,940.00", "STANDARD")]
        [InlineData("CLM-2026-100405", "POL-AUTO-48135", "2026-09-10", "THFT", "$1,253.12", "FRAUD_REVIEW")]
        [InlineData("CLM-2026-100406", "POL-HOME-48142", "2026-09-11", "WIND", "$2,876.72", "FAST_TRACK")]
        [InlineData("CLM-2026-100407", "POL-HOME-48149", "2026-09-12", "WATR", "$8,320.00", "DECLINE_NOT_IN_FORCE")]
        [InlineData("CLM-2026-100408", "POL-HOME-48156", "2026-09-14", "FIRE", "$86,100.00", "LARGE_LOSS")]
        [InlineData("CLM-2026-100409", "POL-HOME-48163", "2026-09-15", "LIAB", "$48,750.00", "STANDARD")]
        [InlineData("CLM-2026-100410", "POL-AUTO-48170", "2026-09-16", "COMP", "$3,300.00", "FRAUD_REVIEW")]
        [InlineData("CLM-2026-100411", "POL-AUTO-48177", "2026-09-17", "GLAS", "$768.00", "DECLINE_NOT_IN_FORCE")]
        [InlineData("CLM-2026-100412", "POL-HOME-48184", "2026-09-18", "WIND", "$4,715.00", "STANDARD")]
        [InlineData("CLM-2026-100413", "POL-AUTO-48191", "2026-09-20", "COLL", "$5,720.00", "FRAUD_REVIEW")]
        [InlineData("CLM-2026-100414", "POL-HOME-48198", "2026-09-21", "THFT", "$2,750.00", "STANDARD")]
        [InlineData("CLM-2026-100415", "POL-AUTO-48205", "2026-09-22", "COLL", "$2,200.00", "DECLINE_NOT_IN_FORCE")]
        public void Claim_rows_match_the_fnol_corpus(string claim, string policy, string lossDate, string cause,
            string reserve, string status)
        {
            ClaimRow row = Load<ClaimListResponse>("claims.json").Claims
                .Select(c => new ClaimRow(c)).Single(r => r.ClaimNumber == claim);
            Assert.Equal(policy, row.PolicyNumber);
            Assert.Equal(lossDate, row.LossDate);
            Assert.Equal(cause, row.CauseCode);
            Assert.Equal(reserve, row.ReserveText);
            Assert.Equal(status, row.Status);
        }

        [Fact]
        public void Totals_are_sums_of_rounded_rows()
        {
            var policies = Load<PolicyListResponse>("policies.json").Policies.Select(p => new PolicyRow(p)).ToList();
            var claims = Load<ClaimListResponse>("claims.json").Claims.Select(c => new ClaimRow(c)).ToList();
            Assert.Equal(5, policies.Count);
            Assert.Equal(15000.00m, policies.Where(p => p.Status == "IN_FORCE").Sum(p => p.Premium));
            Assert.Equal(16, claims.Count);
            Assert.Equal(203648.53m, claims.Sum(c => c.Reserve));
        }
    }
}
