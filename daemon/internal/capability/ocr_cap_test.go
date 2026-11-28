// This file unit-tests the "OCR text recognition" capability (ocr.recognize).
//
// Test strategy: use httptest to start a fake gateway that simulates POST /api/ocr, verifying:
//  1. Local image path: read file -> base64 -> upload, and the base64 the gateway receives matches the source bytes;
//  2. Image URL: the daemon downloads it itself and then uploads it;
//  3. Parameter validation: missing both image/image_url, providing both, and image_url without an http prefix should all error;
//  4. Size limit: a local file exceeding 20 MiB is rejected;
//  5. A clear error when credentials are missing;
//  6. Passing through error when the gateway returns success=false;
//  7. Falling back to the injected authenticated gateway list when gateway is omitted;
//  8. Normalizing the filename extension (non-whitelisted falls back to .png).
//
// Note: this file has no build tag and compiles on both Linux and Windows; it depends only on the standard library.
package capability

import (
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeOcrGateway is a fake gateway that simulates the gateway /api/ocr endpoint.
type fakeOcrGateway struct {
	t *testing.T
	// The expected Token (empty means no validation).
	wantToken string
	// The response body returned by the gateway.
	response map[string]any
	// Records the received request body for assertions.
	gotPayload map[string]any
	// Records the number of received requests.
	calls int
}

func (f *fakeOcrGateway) handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/ocr" {
			http.Error(w, `{"success":false,"error":"not found"}`, http.StatusNotFound)
			return
		}
		if f.wantToken != "" && r.Header.Get("Authorization") != "Bearer "+f.wantToken {
			http.Error(w, `{"success":false,"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			http.Error(w, `{"success":false,"error":"bad json"}`, http.StatusBadRequest)
			return
		}
		f.gotPayload = payload
		f.calls++
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(f.response)
	}
}

// withOcrProvider injects a credential provider with a fixed Token and restores it after the test.
func withOcrProvider(t *testing.T, token string) {
	t.Helper()
	SetBrowserExtCredentialProvider(func(gateway string) (string, bool) {
		if token == "" {
			return "", false
		}
		return token, true
	})
	t.Cleanup(func() { SetBrowserExtCredentialProvider(nil) })
}

// withOcrGatewayList injects a fixed authenticated gateway list and restores it after the test.
func withOcrGatewayList(t *testing.T, gateways []string) {
	t.Helper()
	SetOcrGatewayLister(func() []string { return gateways })
	t.Cleanup(func() { SetOcrGatewayLister(nil) })
}

// writeTempImage writes a fake image in a temp directory and returns the path.
func writeTempImage(t *testing.T, name string, data []byte) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("failed to write the temp image: %v", err)
	}
	return path
}

// TestOcrRecognizeLocalImage verifies the complete chain for a local image path.
func TestOcrRecognizeLocalImage(t *testing.T) {
	imageBytes := []byte("fake-png-bytes-\x89PNG\r\n\x1a\n")
	path := writeTempImage(t, "shot.png", imageBytes)

	fake := &fakeOcrGateway{
		wantToken: "test-token",
		response: map[string]any{
			"success": true,
			"text":    "HAIJUNBOT OCR 12345",
			"backend": "tesseract",
			"lines":   []any{},
			"error":   "",
		},
	}
	srv := httptest.NewServer(fake.handler())
	defer srv.Close()

	withOcrProvider(t, "test-token")

	res, err := handleOcrRecognize(map[string]any{
		"gateway": srv.URL,
		"image":   path,
	})
	if err != nil {
		t.Fatalf("handleOcrRecognize failed: %v", err)
	}
	result, ok := res.(map[string]any)
	if !ok {
		t.Fatalf("wrong return value type: %T", res)
	}
	if result["text"] != "HAIJUNBOT OCR 12345" {
		t.Errorf("text = %v, want HAIJUNBOT OCR 12345", result["text"])
	}
	if result["backend"] != "tesseract" {
		t.Errorf("backend = %v, want tesseract", result["backend"])
	}
	if result["size"] != len(imageBytes) {
		t.Errorf("size = %v, want %d", result["size"], len(imageBytes))
	}
	// Verify that the uploaded base64 matches the source bytes.
	gotB64, _ := fake.gotPayload["image_base64"].(string)
	decoded, err := base64.StdEncoding.DecodeString(gotB64)
	if err != nil {
		t.Fatalf("the base64 the gateway received cannot be decoded: %v", err)
	}
	if string(decoded) != string(imageBytes) {
		t.Errorf("the uploaded bytes do not match the source")
	}
	// filename is inferred from the image path.
	if fake.gotPayload["filename"] != "shot.png" {
		t.Errorf("filename = %v, want shot.png", fake.gotPayload["filename"])
	}
	// When psm is not specified, null should be passed.
	if v, exists := fake.gotPayload["psm"]; !exists || v != nil {
		t.Errorf("psm = %v, want null", v)
	}
	if fake.gotPayload["backend"] != "auto" {
		t.Errorf("backend = %v, want the default auto", fake.gotPayload["backend"])
	}
	if fake.gotPayload["lang"] != "eng" {
		t.Errorf("lang = %v, want the default eng", fake.gotPayload["lang"])
	}
}

// TestOcrRecognizeImageURL verifies that image_url is downloaded by the daemon itself and then uploaded.
func TestOcrRecognizeImageURL(t *testing.T) {
	imageBytes := []byte("remote-image-bytes")
	imgSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write(imageBytes)
	}))
	defer imgSrv.Close()

	fake := &fakeOcrGateway{
		wantToken: "tok",
		response: map[string]any{
			"success": true,
			"text":    "hello",
			"backend": "rapidocr",
			"lines":   []any{},
		},
	}
	ocrSrv := httptest.NewServer(fake.handler())
	defer ocrSrv.Close()

	withOcrProvider(t, "tok")

	res, err := handleOcrRecognize(map[string]any{
		"gateway":   ocrSrv.URL,
		"image_url": imgSrv.URL + "/a.png",
		"filename":  "a.png",
	})
	if err != nil {
		t.Fatalf("handleOcrRecognize failed: %v", err)
	}
	result := res.(map[string]any)
	if result["text"] != "hello" {
		t.Errorf("text = %v, want hello", result["text"])
	}
	gotB64, _ := fake.gotPayload["image_base64"].(string)
	decoded, err := base64.StdEncoding.DecodeString(gotB64)
	if err != nil {
		t.Fatalf("base64 decoding failed: %v", err)
	}
	if string(decoded) != string(imageBytes) {
		t.Errorf("the uploaded bytes do not match the download source")
	}
}

// TestOcrRecognizeGatewayFallback verifies falling back to the authenticated gateway list when gateway is omitted.
func TestOcrRecognizeGatewayFallback(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))

	fake := &fakeOcrGateway{
		wantToken: "tok",
		response:  map[string]any{"success": true, "text": "ok", "backend": "tesseract", "lines": []any{}},
	}
	srv := httptest.NewServer(fake.handler())
	defer srv.Close()

	withOcrProvider(t, "tok")
	withOcrGatewayList(t, []string{srv.URL})

	res, err := handleOcrRecognize(map[string]any{"image": path})
	if err != nil {
		t.Fatalf("handleOcrRecognize failed: %v", err)
	}
	result := res.(map[string]any)
	if result["gateway"] != srv.URL {
		t.Errorf("gateway = %v, want a fallback to %s", result["gateway"], srv.URL)
	}
}

// TestOcrRecognizeNoGateway verifies an error when there is no gateway and no authenticated gateway.
func TestOcrRecognizeNoGateway(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))
	withOcrProvider(t, "tok")
	withOcrGatewayList(t, nil)

	_, err := handleOcrRecognize(map[string]any{"image": path})
	if err == nil {
		t.Fatal("expected an error but actually succeeded")
	}
	if !strings.Contains(err.Error(), "no authenticated gateway") {
		t.Errorf("the error message is not clear: %v", err)
	}
}

// TestOcrRecognizeParamValidation verifies the parameter validation branches.
func TestOcrRecognizeParamValidation(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))
	withOcrProvider(t, "tok")

	cases := []struct {
		name    string
		params  map[string]any
		wantSub string
	}{
		{
			name:    "both missing",
			params:  map[string]any{"gateway": "http://gw"},
			wantSub: "must be provided",
		},
		{
			name:    "both provided",
			params:  map[string]any{"gateway": "http://gw", "image": path, "image_url": "http://x/a.png"},
			wantSub: "not both",
		},
		{
			name:    "image_url is not http",
			params:  map[string]any{"gateway": "http://gw", "image_url": "ftp://x/a.png"},
			wantSub: "must start with http:// or https://",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := handleOcrRecognize(tc.params)
			if err == nil {
				t.Fatal("expected an error but actually succeeded")
			}
			if !strings.Contains(err.Error(), tc.wantSub) {
				t.Errorf("the error message %q does not contain %q", err.Error(), tc.wantSub)
			}
		})
	}
}

// TestOcrRecognizeNoToken verifies an error when credentials are missing.
func TestOcrRecognizeNoToken(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))
	withOcrProvider(t, "") // no credentials

	_, err := handleOcrRecognize(map[string]any{"gateway": "http://gw.example.com", "image": path})
	if err == nil {
		t.Fatal("expected an error but actually succeeded")
	}
	if !strings.Contains(err.Error(), "no available credentials") {
		t.Errorf("the error message is not clear: %v", err)
	}
}

// TestOcrRecognizeLocalFileMissing verifies an error when the local file does not exist.
func TestOcrRecognizeLocalFileMissing(t *testing.T) {
	withOcrProvider(t, "tok")
	_, err := handleOcrRecognize(map[string]any{
		"gateway": "http://gw.example.com",
		"image":   filepath.Join(t.TempDir(), "not-exist.png"),
	})
	if err == nil {
		t.Fatal("expected an error but actually succeeded")
	}
	if !strings.Contains(err.Error(), "failed to read local image") {
		t.Errorf("the error message is not clear: %v", err)
	}
}

// TestOcrRecognizeGatewayFailure verifies passing through error when the gateway returns success=false.
func TestOcrRecognizeGatewayFailure(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))
	fake := &fakeOcrGateway{
		wantToken: "tok",
		response: map[string]any{
			"success": false,
			"error":   "no available OCR backend",
		},
	}
	srv := httptest.NewServer(fake.handler())
	defer srv.Close()
	withOcrProvider(t, "tok")

	_, err := handleOcrRecognize(map[string]any{"gateway": srv.URL, "image": path})
	if err == nil {
		t.Fatal("expected an error but actually succeeded")
	}
	if !strings.Contains(err.Error(), "no available OCR backend") {
		t.Errorf("the gateway error was not passed through: %v", err)
	}
}

// TestOcrRecognizeOversizeLocalFile verifies a local file exceeding 20 MiB is rejected (no request is made).
func TestOcrRecognizeOversizeLocalFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "big.png")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("failed to create the big file: %v", err)
	}
	// Truncate to only 20 MiB + 1 byte to avoid the test being too slow.
	if err := f.Truncate(ocrMaxImageBytes + 1); err != nil {
		f.Close()
		t.Fatalf("truncate failed: %v", err)
	}
	f.Close()

	fake := &fakeOcrGateway{wantToken: "tok", response: map[string]any{"success": true}}
	srv := httptest.NewServer(fake.handler())
	defer srv.Close()
	withOcrProvider(t, "tok")

	_, err = handleOcrRecognize(map[string]any{"gateway": srv.URL, "image": path})
	if err == nil {
		t.Fatal("expected an error but actually succeeded")
	}
	if !strings.Contains(err.Error(), "exceeding the limit") {
		t.Errorf("the error message is not clear: %v", err)
	}
	if fake.calls != 0 {
		t.Errorf("no request should be made when over the limit, actual %d", fake.calls)
	}
}

// TestOcrRecognizeDetailAndPsm verifies passing through detail/psm.
func TestOcrRecognizeDetailAndPsm(t *testing.T) {
	path := writeTempImage(t, "x.png", []byte("bytes"))
	fake := &fakeOcrGateway{
		wantToken: "tok",
		response: map[string]any{
			"success": true,
			"text":    "ok",
			"backend": "tesseract",
			"lines":   []any{map[string]any{"text": "ok", "confidence": 0.9}},
		},
	}
	srv := httptest.NewServer(fake.handler())
	defer srv.Close()
	withOcrProvider(t, "tok")

	res, err := handleOcrRecognize(map[string]any{
		"gateway": srv.URL,
		"image":   path,
		"psm":     float64(7), // simulate the numeric type after JSON deserialization
		"detail":  true,
		"lang":    "chi_sim+eng",
	})
	if err != nil {
		t.Fatalf("handleOcrRecognize failed: %v", err)
	}
	if fake.gotPayload["psm"] != float64(7) {
		t.Errorf("psm = %v, want 7", fake.gotPayload["psm"])
	}
	if fake.gotPayload["detail"] != true {
		t.Errorf("detail = %v, want true", fake.gotPayload["detail"])
	}
	if fake.gotPayload["lang"] != "chi_sim+eng" {
		t.Errorf("lang = %v, want chi_sim+eng", fake.gotPayload["lang"])
	}
	result := res.(map[string]any)
	lines, ok := result["lines"].([]any)
	if !ok || len(lines) != 1 {
		t.Errorf("lines = %v, want 1 entry", result["lines"])
	}
}

// TestOcrNormalizeFilename verifies extension whitelist normalization.
func TestOcrNormalizeFilename(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"a.png", "a.png"},
		{"a.JPG", "a.JPG"},
		{"a.jpeg", "a.jpeg"},
		{"a.webp", "a.webp"},
		{"a.txt", "a.png"},     // non-whitelisted -> fall back to .png
		{"noext", "noext.png"}, // no extension -> append .png
		{"a.b.c.tif", "a.b.c.tif"},
	}
	for _, tc := range cases {
		if got := ocrNormalizeFilename(tc.in); got != tc.want {
			t.Errorf("ocrNormalizeFilename(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

// TestOcrCapabilityRegistered verifies that the capability is registered with a complete parameter schema.
func TestOcrCapabilityRegistered(t *testing.T) {
	reg := NewRegistry()
	cap, ok := reg.Get("ocr.recognize")
	if !ok {
		t.Fatal("ocr.recognize is not registered")
	}
	if cap.Handler == nil {
		t.Fatal("ocr.recognize Handler is nil")
	}
	props, ok := cap.Parameters["properties"].(map[string]any)
	if !ok {
		t.Fatal("the parameter schema is missing properties")
	}
	for _, key := range []string{"gateway", "image", "image_url", "filename", "backend", "lang", "psm", "detail"} {
		if _, exists := props[key]; !exists {
			t.Errorf("the parameter schema is missing %s", key)
		}
	}
}

// TestOcrListGatewaysNotInjected verifies the safe behavior when not injected.
func TestOcrListGatewaysNotInjected(t *testing.T) {
	SetOcrGatewayLister(nil)
	if got := ocrListGateways(); got != nil {
		t.Errorf("it should return nil when not injected, actual %v", got)
	}
}

// Ensure io is used (the fake gateway response reading path).
var _ = io.Discard
