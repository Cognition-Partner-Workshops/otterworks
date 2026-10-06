// Package chaos reads the per-tenant chaos flags the demo tooling sets in the
// tenant's Redis (scripts/inject-bug.sh). Reads are cached for a short window
// so a request never pays a Redis round trip, and an unreachable Redis reads
// as "off" with a back-off, matching services/document-service/app/chaos.py.
package chaos

import (
	"context"
	"errors"
	"strconv"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// FlagMobileLatencyMS holds the delay, in milliseconds, injected in front of
// native-app reads of the file list.
const FlagMobileLatencyMS = "chaos:api-gateway:mobile_latency_ms"

const (
	flagCacheTTL       = 2 * time.Second
	flagFailureBackoff = 15 * time.Second
	redisTimeout       = 250 * time.Millisecond
	maxInjectedDelay   = 30 * time.Second
)

// Getter is the slice of a Redis client the flag reader needs.
type Getter interface {
	Get(ctx context.Context, key string) (string, error)
}

// ErrNotFound is returned by a Getter when the key does not exist.
var ErrNotFound = errors.New("chaos: flag not set")

type cached struct {
	expires time.Time
	value   string
}

// Flags is a cached reader over a Getter. The zero value and a nil *Flags both
// read every flag as off.
type Flags struct {
	getter Getter
	now    func() time.Time

	mu    sync.Mutex
	cache map[string]cached
}

// New returns a Flags reading through getter. A nil getter disables chaos.
func New(getter Getter) *Flags {
	return &Flags{getter: getter, now: time.Now, cache: map[string]cached{}}
}

// NewRedis returns a Flags backed by the Redis at addr, or a disabled reader
// when addr is empty.
func NewRedis(addr string) *Flags {
	if addr == "" {
		return New(nil)
	}
	client := redis.NewClient(&redis.Options{
		Addr:         addr,
		DialTimeout:  redisTimeout,
		ReadTimeout:  redisTimeout,
		WriteTimeout: redisTimeout,
		MaxRetries:   -1,
	})
	return New(redisGetter{client})
}

// MobileLatency returns the delay to inject for native-app file list reads,
// or 0 when the flag is unset or unreadable.
func (f *Flags) MobileLatency(ctx context.Context) time.Duration {
	raw := f.get(ctx, FlagMobileLatencyMS)
	if raw == "" {
		return 0
	}
	ms, err := strconv.Atoi(raw)
	if err != nil || ms <= 0 {
		return 0
	}
	d := time.Duration(ms) * time.Millisecond
	if d > maxInjectedDelay {
		d = maxInjectedDelay
	}
	return d
}

func (f *Flags) get(ctx context.Context, key string) string {
	if f == nil || f.getter == nil {
		return ""
	}
	now := f.now()
	f.mu.Lock()
	if c, ok := f.cache[key]; ok && now.Before(c.expires) {
		f.mu.Unlock()
		return c.value
	}
	f.mu.Unlock()

	ctx, cancel := context.WithTimeout(ctx, redisTimeout)
	defer cancel()
	value, err := f.getter.Get(ctx, key)
	ttl := flagCacheTTL
	switch {
	case errors.Is(err, ErrNotFound):
		value = ""
	case err != nil:
		value = ""
		ttl = flagFailureBackoff
	}

	f.mu.Lock()
	f.cache[key] = cached{expires: now.Add(ttl), value: value}
	f.mu.Unlock()
	return value
}

type redisGetter struct{ client *redis.Client }

func (g redisGetter) Get(ctx context.Context, key string) (string, error) {
	v, err := g.client.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		return "", ErrNotFound
	}
	return v, err
}
