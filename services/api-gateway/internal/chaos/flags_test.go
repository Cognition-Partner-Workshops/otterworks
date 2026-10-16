package chaos

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

type fakeGetter struct {
	values map[string]string
	err    error
	calls  int
}

func (g *fakeGetter) Get(_ context.Context, key string) (string, error) {
	g.calls++
	if g.err != nil {
		return "", g.err
	}
	v, ok := g.values[key]
	if !ok {
		return "", ErrNotFound
	}
	return v, nil
}

func TestMobileLatency(t *testing.T) {
	cases := map[string]struct {
		value string
		want  time.Duration
	}{
		"milliseconds":  {"3000", 3 * time.Second},
		"non numeric":   {"yes", 0},
		"zero":          {"0", 0},
		"negative":      {"-5", 0},
		"capped at 30s": {"600000", 30 * time.Second},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			f := New(&fakeGetter{values: map[string]string{FlagMobileLatencyMS: tc.value}})
			assert.Equal(t, tc.want, f.MobileLatency(context.Background()))
		})
	}
}

func TestMobileLatencyUnsetOrDisabled(t *testing.T) {
	assert.Zero(t, New(&fakeGetter{}).MobileLatency(context.Background()))
	assert.Zero(t, New(nil).MobileLatency(context.Background()))
	var nilFlags *Flags
	assert.Zero(t, nilFlags.MobileLatency(context.Background()))
}

func TestFlagReadsAreCached(t *testing.T) {
	g := &fakeGetter{values: map[string]string{FlagMobileLatencyMS: "3000"}}
	f := New(g)
	now := time.Unix(1000, 0)
	f.now = func() time.Time { return now }

	f.MobileLatency(context.Background())
	f.MobileLatency(context.Background())
	assert.Equal(t, 1, g.calls)

	now = now.Add(flagCacheTTL + time.Millisecond)
	f.MobileLatency(context.Background())
	assert.Equal(t, 2, g.calls)
}

func TestRedisErrorReadsAsOffWithBackoff(t *testing.T) {
	g := &fakeGetter{err: errors.New("connection refused")}
	f := New(g)
	now := time.Unix(1000, 0)
	f.now = func() time.Time { return now }

	assert.Zero(t, f.MobileLatency(context.Background()))
	now = now.Add(flagCacheTTL + time.Millisecond)
	assert.Zero(t, f.MobileLatency(context.Background()))
	assert.Equal(t, 1, g.calls, "a failed read backs off for longer than the cache window")
}
