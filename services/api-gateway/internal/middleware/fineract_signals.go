package middleware

import (
	"container/list"
	"crypto/sha256"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"
)

const makerCheckerLimit = 10000
const makerCheckerWindow = 10 * time.Second

var makerCheckerPath = regexp.MustCompile(`(?:^|/)makercheckers/([^/]+)/?$`)
var configurationPath = regexp.MustCompile(`(?:^|/)configurations/(?:[^/]+|name/maker-checker)/?$`)
var deregisterPath = regexp.MustCompile(`(?:^|/)datatables/deregister/.+$`)
var creditReportPath = regexp.MustCompile(`(?:^|/)creditBureauIntegration/addCreditReport/?$`)

type approvalObservation struct {
	key [32]byte
	at  time.Time
}

type makerCheckerTracker struct {
	mu    sync.Mutex
	ids   map[[32]byte]*list.Element
	order *list.List
	now   func() time.Time
}

func newMakerCheckerTracker() *makerCheckerTracker {
	return &makerCheckerTracker{
		ids: make(map[[32]byte]*list.Element), order: list.New(), now: time.Now,
	}
}

func (s *makerCheckerTracker) approve(id string) bool {
	key := sha256.Sum256([]byte(id))
	s.mu.Lock()
	defer s.mu.Unlock()
	now := s.now()
	for first := s.order.Front(); first != nil; first = s.order.Front() {
		observation := first.Value.(approvalObservation)
		if now.Sub(observation.at) < makerCheckerWindow {
			break
		}
		delete(s.ids, observation.key)
		s.order.Remove(first)
	}
	if previous, ok := s.ids[key]; ok {
		previous.Value = approvalObservation{key: key, at: now}
		s.order.MoveToBack(previous)
		return true
	}
	if len(s.ids) == makerCheckerLimit {
		first := s.order.Front()
		delete(s.ids, first.Value.(approvalObservation).key)
		s.order.Remove(first)
	}
	s.ids[key] = s.order.PushBack(approvalObservation{key: key, at: now})
	return false
}

func ObserveFineractSignals() func(http.Handler) http.Handler {
	return observeFineractSignals(newMakerCheckerTracker())
}

func observeFineractSignals(tracker *makerCheckerTracker) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			path := r.URL.Path
			if r.Method == http.MethodPost {
				command := r.URL.Query().Get("command")
				if match := makerCheckerPath.FindStringSubmatch(path); match != nil && command == "approve" {
					if tracker.approve(match[1]) {
						securityEvents.WithLabelValues("fineract_makerchecker_repeat_approve", "within_window").Inc()
					}
				}
				if configurationPath.MatchString(path) && command == "disable" {
					securityEvents.WithLabelValues("fineract_maker_checker_disabled", "command_disable").Inc()
				}
				if deregisterPath.MatchString(path) {
					securityEvents.WithLabelValues("fineract_privileged_endpoint", "datatable_deregister").Inc()
				}
				if creditReportPath.MatchString(path) {
					securityEvents.WithLabelValues("fineract_privileged_endpoint", "credit_report_add").Inc()
				}
			}
			if r.Method == http.MethodPut && strings.HasSuffix(strings.TrimSuffix(path, "/"), "/configurations/name/maker-checker") {
				if string(observedJSONBody(r)["enabled"]) == "false" {
					securityEvents.WithLabelValues("fineract_maker_checker_disabled", "config_put").Inc()
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}
