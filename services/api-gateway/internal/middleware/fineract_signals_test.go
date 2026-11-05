package middleware

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestFineractSignals(t *testing.T) {
	for _, prefix := range []string{"", "/api/v1", "/fineract-provider/api/v1"} {
		for _, tc := range []struct {
			name, method, path, body, event, reason string
			previous                                string
		}{
			{name: "single approve", method: "POST", path: "/makercheckers/1?command=approve"},
			{name: "different ids", method: "POST", previous: "/makercheckers/2?command=approve", path: "/makercheckers/1?command=approve"},
			{name: "approve then reject", method: "POST", previous: "/makercheckers/1?command=approve", path: "/makercheckers/1?command=reject"},
			{name: "repeat approve", method: "POST", previous: "/makercheckers/1?command=approve", path: "/makercheckers/1?command=approve", event: "fineract_makerchecker_repeat_approve", reason: "within_window"},
			{name: "get approve", method: "GET", path: "/makercheckers/1?command=approve"},
			{name: "missing id", method: "POST", path: "/makercheckers/?command=approve"},
			{name: "configuration false", method: "PUT", path: "/configurations/name/maker-checker", body: `{"enabled":false}`, event: "fineract_maker_checker_disabled", reason: "config_put"},
			{name: "configuration true", method: "PUT", path: "/configurations/name/maker-checker", body: `{"enabled":true}`},
			{name: "configuration string false", method: "PUT", path: "/configurations/name/maker-checker", body: `{"enabled":"false"}`},
			{name: "configuration empty", method: "PUT", path: "/configurations/name/maker-checker"},
			{name: "configuration missing enabled", method: "PUT", path: "/configurations/name/maker-checker", body: `{}`},
			{name: "configuration non JSON", method: "PUT", path: "/configurations/name/maker-checker", body: "enabled=false"},
			{name: "configuration oversized", method: "PUT", path: "/configurations/name/maker-checker", body: `{"enabled":false,"padding":"` + strings.Repeat("x", paymentBodyLimit) + `"}`},
			{name: "other config", method: "PUT", path: "/configurations/name/other", body: `{"enabled":false}`},
			{name: "disable id", method: "POST", path: "/configurations/1?command=disable", event: "fineract_maker_checker_disabled", reason: "command_disable"},
			{name: "disable name", method: "POST", path: "/configurations/name/maker-checker?command=disable", event: "fineract_maker_checker_disabled", reason: "command_disable"},
			{name: "enable command", method: "POST", path: "/configurations/1?command=enable"},
			{name: "get disable", method: "GET", path: "/configurations/1?command=disable"},
			{name: "deregister", method: "POST", path: "/datatables/deregister/replay-table", event: "fineract_privileged_endpoint", reason: "datatable_deregister"},
			{name: "get deregister", method: "GET", path: "/datatables/deregister/replay-table"},
			{name: "credit report", method: "POST", path: "/creditBureauIntegration/addCreditReport", event: "fineract_privileged_endpoint", reason: "credit_report_add"},
			{name: "get credit report", method: "GET", path: "/creditBureauIntegration/addCreditReport"},
			{name: "other endpoint", method: "POST", path: "/other/1?command=approve"},
		} {
			t.Run(prefix+"/"+tc.name, func(t *testing.T) {
				next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					body, err := io.ReadAll(r.Body)
					require.NoError(t, err)
					require.Equal(t, "unchanged", r.Header.Get("X-Test"))
					w.Header().Set("X-Response", "unchanged")
					w.WriteHeader(404)
					_, _ = w.Write(body)
				})
				h := observeFineractSignals(newMakerCheckerTracker())(next)
				request := func(method, path, body string) *http.Request {
					r := httptest.NewRequest(method, prefix+path, strings.NewReader(body))
					r.Header.Set("X-Test", "unchanged")
					return r
				}
				if tc.previous != "" {
					h.ServeHTTP(httptest.NewRecorder(), request("POST", tc.previous, ""))
				}
				events := map[string][]string{
					"fineract_makerchecker_repeat_approve": {"within_window"},
					"fineract_maker_checker_disabled":      {"config_put", "command_disable"},
					"fineract_privileged_endpoint":         {"datatable_deregister", "credit_report_add"},
				}
				before := map[string]float64{}
				for event, reasons := range events {
					for _, reason := range reasons {
						before[event+"/"+reason] = counterValue(securityEvents.WithLabelValues(event, reason))
					}
				}
				control, response := httptest.NewRecorder(), httptest.NewRecorder()
				next.ServeHTTP(control, request(tc.method, tc.path, tc.body))
				h.ServeHTTP(response, request(tc.method, tc.path, tc.body))
				require.Equal(t, control.Code, response.Code)
				require.Equal(t, control.Header(), response.Header())
				require.Equal(t, control.Body.String(), response.Body.String())
				for event, reasons := range events {
					for _, reason := range reasons {
						delta := 0.0
						if event == tc.event && reason == tc.reason {
							delta = 1
						}
						require.Equal(t, before[event+"/"+reason]+delta, counterValue(securityEvents.WithLabelValues(event, reason)))
					}
				}
			})
		}
	}
}

func TestMakerCheckerBoundAndExpiry(t *testing.T) {
	tracker := newMakerCheckerTracker()
	now := time.Now()
	tracker.now = func() time.Time { return now }
	for i := 0; i <= makerCheckerLimit; i++ {
		require.False(t, tracker.approve(fmt.Sprint(i)))
	}
	require.Len(t, tracker.ids, makerCheckerLimit)
	require.Equal(t, makerCheckerLimit, tracker.order.Len())
	require.False(t, tracker.approve("0"))
	require.True(t, tracker.approve("0"))
	now = now.Add(makerCheckerWindow)
	require.False(t, tracker.approve("0"))
	require.Len(t, tracker.ids, 1)
	require.Equal(t, 1, tracker.order.Len())
}

func TestMakerCheckerConcurrentAndPrefixIndependent(t *testing.T) {
	tracker := newMakerCheckerTracker()
	var repeated atomic.Int64
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if tracker.approve("same-id") {
				repeated.Add(1)
			}
		}()
	}
	wg.Wait()
	require.Equal(t, int64(99), repeated.Load())
	counter := securityEvents.WithLabelValues("fineract_makerchecker_repeat_approve", "within_window")
	before := counterValue(counter)
	h := ObserveFineractSignals()(http.NotFoundHandler())
	for _, prefix := range []string{"/fineract-provider/api/v1", "/api/v1", ""} {
		h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("POST", prefix+"/makercheckers/7?command=approve", nil))
	}
	require.Equal(t, before+2, counterValue(counter))
}

type fineractErrorBody struct{ closed bool }

func (*fineractErrorBody) Read(p []byte) (int, error) {
	return copy(p, `{"enabled":false}`), io.ErrUnexpectedEOF
}
func (b *fineractErrorBody) Close() error { b.closed = true; return nil }

func TestFineractReadErrorAndLimiterPreservation(t *testing.T) {
	body := &fineractErrorBody{}
	r := httptest.NewRequest("PUT", "/configurations/name/maker-checker", nil)
	r.Body = body
	counter := securityEvents.WithLabelValues("fineract_maker_checker_disabled", "config_put")
	before := counterValue(counter)
	h := ObserveFineractSignals()(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data, err := io.ReadAll(r.Body)
		require.ErrorIs(t, err, io.ErrUnexpectedEOF)
		require.Equal(t, `{"enabled":false}`, string(data))
		require.NoError(t, r.Body.Close())
		w.WriteHeader(404)
	}))
	h.ServeHTTP(httptest.NewRecorder(), r)
	require.True(t, body.closed)
	require.Equal(t, before, counterValue(counter))
	limiter := &RateLimiter{buckets: make(map[string]*TokenBucket), rps: 0, now: time.Now}
	h = ObserveFineractSignals()(limiter.Handler(http.NotFoundHandler()))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest("PUT", "/configurations/name/maker-checker", strings.NewReader(`{"enabled":false}`)))
	require.Equal(t, 429, w.Code)
	require.Equal(t, before+1, counterValue(counter))
}
