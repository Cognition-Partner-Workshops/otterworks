using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Thistlecombe.AgentDesktop.Models
{
    /// <summary>A row of <c>policies</c> joined to <c>products</c> (02_seed.sql). Money arrives as a decimal string.</summary>
    public class Policy
    {
        [JsonPropertyName("policy_no")] public string? PolicyNo { get; set; }
        [JsonPropertyName("product_code")] public string? ProductCode { get; set; }
        [JsonPropertyName("product_name")] public string? ProductName { get; set; }
        [JsonPropertyName("line_of_business")] public string? LineOfBusiness { get; set; }
        [JsonPropertyName("holder_name")] public string? HolderName { get; set; }
        [JsonPropertyName("annual_premium")] public decimal AnnualPremium { get; set; }
        [JsonPropertyName("issued_date")] public string? IssuedDate { get; set; }
        [JsonPropertyName("status")] public string? Status { get; set; }
    }

    public class PolicyListResponse
    {
        [JsonPropertyName("policies")] public List<Policy> Policies { get; set; } = new List<Policy>();
        [JsonPropertyName("total")] public int Total { get; set; }
    }

    /// <summary>An FNOL claim from the claims hub: canonical claim, triage-facts reserve and triage outcome.</summary>
    public class Claim
    {
        [JsonPropertyName("claim_number")] public string? ClaimNumber { get; set; }
        [JsonPropertyName("policy_number")] public string? PolicyNumber { get; set; }
        [JsonPropertyName("line_of_business")] public string? LineOfBusiness { get; set; }
        [JsonPropertyName("claimant_name")] public string? ClaimantName { get; set; }
        [JsonPropertyName("loss_date")] public string? LossDate { get; set; }
        [JsonPropertyName("reported_date")] public string? ReportedDate { get; set; }
        [JsonPropertyName("cause_code")] public string? CauseCode { get; set; }
        [JsonPropertyName("estimated_amount")] public decimal EstimatedAmount { get; set; }
        [JsonPropertyName("injury")] public bool Injury { get; set; }
        [JsonPropertyName("reserve")] public decimal Reserve { get; set; }
        [JsonPropertyName("status")] public string? Status { get; set; }
    }

    public class ClaimListResponse
    {
        [JsonPropertyName("claims")] public List<Claim> Claims { get; set; } = new List<Claim>();
        [JsonPropertyName("total")] public int Total { get; set; }
    }
}
