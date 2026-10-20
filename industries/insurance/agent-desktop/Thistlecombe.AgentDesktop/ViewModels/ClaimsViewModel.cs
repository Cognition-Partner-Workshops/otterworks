using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Thistlecombe.AgentDesktop.Models;
using Thistlecombe.AgentDesktop.Services;

namespace Thistlecombe.AgentDesktop.ViewModels
{
    public class ClaimsViewModel : LedgerViewModel<ClaimRow>
    {
        private readonly InsuranceApiClient _api;

        public ClaimsViewModel(InsuranceApiClient api)
        {
            _api = api;
            _ = LoadAsync();
        }

        protected override async Task<IReadOnlyList<ClaimRow>> FetchAsync()
        {
            ClaimListResponse response = await _api.GetClaimsAsync();
            return response.Claims.Select(c => new ClaimRow(c)).ToList();
        }

        protected override string Summarize(IReadOnlyList<ClaimRow> rows)
        {
            return string.Format("{0} claims · {1} total reserve · {2} fast track · {3} fraud review",
                rows.Count, CarrierMoney.Format(rows.Sum(r => r.Reserve)),
                rows.Count(r => r.Status == "FAST_TRACK"), rows.Count(r => r.Status == "FRAUD_REVIEW"));
        }
    }
}
