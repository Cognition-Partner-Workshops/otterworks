using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Thistlecombe.AgentDesktop.Models;
using Thistlecombe.AgentDesktop.Services;

namespace Thistlecombe.AgentDesktop.ViewModels
{
    public class PoliciesViewModel : LedgerViewModel<PolicyRow>
    {
        private readonly InsuranceApiClient _api;

        public PoliciesViewModel(InsuranceApiClient api)
        {
            _api = api;
            _ = LoadAsync();
        }

        protected override async Task<IReadOnlyList<PolicyRow>> FetchAsync()
        {
            PolicyListResponse response = await _api.GetPoliciesAsync();
            return response.Policies.Select(p => new PolicyRow(p)).ToList();
        }

        protected override string Summarize(IReadOnlyList<PolicyRow> rows)
        {
            List<PolicyRow> inForce = rows.Where(r => r.Status == "IN_FORCE").ToList();
            return string.Format("{0} policies · {1} in force · {2} in-force annual premium",
                rows.Count, inForce.Count, CarrierMoney.Format(inForce.Sum(r => r.Premium)));
        }
    }
}
