package middleware

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoggerWritesClientTaggedJSON(t *testing.T) {
	var buf bytes.Buffer
	h := Logger(zerolog.New(&buf))(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/api/v1/files/?folder_id=1", nil)
	req.Header.Set("User-Agent", iosAppUA)
	h.ServeHTTP(httptest.NewRecorder(), req)

	var line map[string]any
	require.NoError(t, json.Unmarshal(buf.Bytes(), &line))
	assert.Equal(t, "GET", line["method"])
	assert.Equal(t, "/api/v1/files", line["route"])
	assert.Equal(t, float64(http.StatusOK), line["status"])
	assert.Equal(t, "ios", line["client"])
	assert.Contains(t, line, "duration_ms")
	assert.IsType(t, float64(0), line["duration_ms"])
}
