package capability

// This file implements the "OCR text recognition" capability (ocr.recognize), shared across platforms.
//
// Why put recognition on the gateway rather than the local machine: OCR backends (tesseract / rapidocr / paddleocr /
// easyocr / vision) are large and have many dependencies, so installing them on every controlled terminal is unrealistic;
// the gateway side already has a ready-made OcrTool (src/haijunbot/haijunbot_tools/ocr.py) and a POST /api/ocr interface.
// Therefore the daemon is only responsible for "sending the image bytes over", and recognition is done by the gateway.
//
// Data path:
//
//	local image (path or URL) --(read/download)--> base64 --(HTTP, with gateway Token)--> gateway /api/ocr
//
// Important: this file has **no build tag** and is compiled into all platforms (including darwin), so it may only use
// the standard library and must not reference platform-specific symbols (requiredString / optionalBool, etc.).
// Parameter reading reuses the cross-platform shared browserExtOptionalString / transferParamString /
// transferParamInt64 / transferParamBool.

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"haijunbot-daemon/internal/proxy"
)

// ocrMaxImageBytes is the maximum number of bytes of an image allowed to be sent to the gateway (20 MiB).
//
// Rationale: consistent with the gateway-side OCR tool's upper bound (CONTENT_CONFIG.max_image_size defaults to 20 MiB).
// Intercepting locally first avoids needlessly pushing an oversized image that is doomed to be rejected over the network
// after base64 encoding (which expands it by about 4/3).
const ocrMaxImageBytes int64 = 20 << 20 // 20 MiB

// ocrHTTPTimeout is the timeout for a single OCR request.
//
// Rationale: OCR may run the tesseract CLI or hand the image to a vision model, taking anywhere from a few seconds to
// tens of seconds; 60s is a compromise between "a slow backend can finish" and "the caller does not wait forever".
// Note: this is the timeout for the "entire request", including uploading the base64 and waiting for the recognition result.
const ocrHTTPTimeout = 60 * time.Second

// ocrDownloadTimeout is the timeout for downloading an image at image_url.
//
// Shorter than the OCR request: downloading an image is just moving bytes, and 30s is plenty; if the origin server is slow,
// it is better to fail than to stall the entire capability call.
const ocrDownloadTimeout = 30 * time.Second

// ocrDefaultFilename is the default filename used when filename is not provided.
//
// It must have an extension: the gateway decides the temporary file suffix by extension, which in turn affects the OCR backend's decoding path.
const ocrDefaultFilename = "image.png"

// ocrSupportedExts is the whitelist of image extensions allowed on the gateway side (aligned with _SUPPORTED_EXTS in ocr.py).
//
// Validating locally first has the benefit that the error message is closer to the caller (pointing out that filename is wrong),
// rather than waiting for the gateway to return a generic failure. Non-whitelisted extensions fall back to .png.
var ocrSupportedExts = map[string]bool{
	".png":  true,
	".jpg":  true,
	".jpeg": true,
	".bmp":  true,
	".tif":  true,
	".tiff": true,
	".webp": true,
	".gif":  true,
	".pbm":  true,
	".pgm":  true,
	".ppm":  true,
}

// registerOcr registers the OCR capability for the specified platform.
//
// The platform difference is only in the Platform field, and the logic is fully shared, so registry_*.go passes in the platform.
func registerOcr(reg *Registry, platform Platform) {
	_ = reg.Register(Capability{
		Name: "ocr.recognize",
		Description: "Recognizes text in an image (OCR). Hands a local image (a local path or an image URL) to the gateway's OCR service and " +
			"returns the recognized text. Typical use: extract text from a local UI screenshot and use it to decide subsequent click/input positions. " +
			"Image limit 20 MiB; exactly one of image and image_url is required.",
		Platform: platform,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"gateway": map[string]any{
					"type": "string",
					"description": "Gateway address (such as https://hjb-ai.cn). " +
						"When omitted, the first gateway the daemon has authenticated with is used (with multiple gateways, the first by address order).",
				},
				"image": map[string]any{
					"type":        "string",
					"description": "Local image path (such as /tmp/shot.png or C:\\\\tmp\\\\shot.png). Choose one of this and image_url.",
				},
				"image_url": map[string]any{
					"type":        "string",
					"description": "Image URL (http/https). Choose one of this and image; the daemon downloads it itself and then uploads it to the gateway.",
				},
				"filename": map[string]any{
					"type": "string",
					"description": "Filename, used to infer the image extension (default image.png). " +
						"Supports png/jpg/jpeg/bmp/tif/tiff/webp/gif/pbm/pgm/ppm; anything else is treated as .png.",
				},
				"backend": map[string]any{
					"type": "string",
					"description": "OCR backend: auto (default, automatically selected by priority) / tesseract / rapidocr / " +
						"paddleocr / easyocr / vision.",
				},
				"lang": map[string]any{
					"type":        "string",
					"description": "Recognition language, default eng; tesseract supports combinations such as chi_sim+eng.",
				},
				"psm": map[string]any{
					"type":        "integer",
					"description": "tesseract page segmentation mode (3=full auto, 6=single block of text, 7=single line, 11=sparse text).",
				},
				"detail": map[string]any{
					"type":        "boolean",
					"description": "Whether to return per-line details (text/confidence/coordinates, depending on backend capability), default false.",
				},
			},
			"required": []string{},
		},
		Handler: handleOcrRecognize,
	})
}

// ocrParams is the normalized input parsed from the capability parameters.
type ocrParams struct {
	Gateway  string
	Image    string
	ImageURL string
	Filename string
	Backend  string
	Lang     string
	PSM      int64
	HasPSM   bool
	Detail   bool
}

// parseOcrParams parses and validates the parameters of ocr.recognize.
//
// Validation rules:
//   - exactly one of image and image_url must be provided (missing or both provided is an error, to avoid ambiguous semantics);
//   - image_url must start with http:// or https://;
//   - psm is passed through only when explicitly provided (when not provided, null is passed so the gateway uses the backend default).
func parseOcrParams(params map[string]any) (*ocrParams, error) {
	gateway, err := browserExtOptionalString(params, "gateway")
	if err != nil {
		return nil, err
	}
	image, err := browserExtOptionalString(params, "image")
	if err != nil {
		return nil, err
	}
	imageURL, err := browserExtOptionalString(params, "image_url")
	if err != nil {
		return nil, err
	}
	image = strings.TrimSpace(image)
	imageURL = strings.TrimSpace(imageURL)
	if image == "" && imageURL == "" {
		return nil, fmt.Errorf("one of parameter image (a local path) and image_url (an image URL) must be provided")
	}
	if image != "" && imageURL != "" {
		return nil, fmt.Errorf("only one of parameter image and image_url may be provided, not both")
	}
	if imageURL != "" {
		lower := strings.ToLower(imageURL)
		if !strings.HasPrefix(lower, "http://") && !strings.HasPrefix(lower, "https://") {
			return nil, fmt.Errorf("parameter image_url must start with http:// or https://, actual %s", imageURL)
		}
	}
	filename, err := browserExtOptionalString(params, "filename")
	if err != nil {
		return nil, err
	}
	filename = strings.TrimSpace(filename)
	if filename == "" {
		// When unspecified, infer from the image path as much as possible so the gateway gets a more fitting extension.
		if image != "" {
			filename = filepath.Base(image)
		}
		if filename == "" || filename == "." || filename == string(filepath.Separator) {
			filename = ocrDefaultFilename
		}
	}
	backend, err := browserExtOptionalString(params, "backend")
	if err != nil {
		return nil, err
	}
	backend = strings.TrimSpace(backend)
	if backend == "" {
		backend = "auto"
	}
	lang, err := browserExtOptionalString(params, "lang")
	if err != nil {
		return nil, err
	}
	lang = strings.TrimSpace(lang)
	if lang == "" {
		lang = "eng"
	}
	psm, err := transferParamInt64(params, "psm", 0)
	if err != nil {
		return nil, err
	}
	// psm is passed through only when the caller explicitly provides it: 0 is a legal value for tesseract (auto),
	// so 0 cannot represent "not set"; therefore HasPSM is used separately to mark it.
	// Explicitly passing null is equivalent to not being set (null and omitted are semantically the same in JSON).
	hasPSM := false
	if v, ok := params["psm"]; ok && v != nil {
		hasPSM = true
	}
	detail, err := transferParamBool(params, "detail", false)
	if err != nil {
		return nil, err
	}
	return &ocrParams{
		Gateway:  strings.TrimRight(gateway, "/"),
		Image:    image,
		ImageURL: imageURL,
		Filename: filename,
		Backend:  backend,
		Lang:     lang,
		PSM:      psm,
		HasPSM:   hasPSM,
		Detail:   detail,
	}, nil
}

// ocrNormalizeFilename collapses filename to an extension within the whitelist.
//
// The gateway decides the temporary file suffix by extension; non-whitelisted ones (such as .txt, no extension) uniformly fall back to .png,
// consistent with the gateway side, to avoid a mismatch where "local passes but the gateway rejects".
func ocrNormalizeFilename(name string) string {
	ext := strings.ToLower(filepath.Ext(name))
	if ocrSupportedExts[ext] {
		return name
	}
	base := strings.TrimSuffix(name, filepath.Ext(name))
	if base == "" {
		base = "image"
	}
	return base + ".png"
}

// ocrReadLocalImage reads the bytes of a local image and validates the size.
func ocrReadLocalImage(path string) ([]byte, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read local image %s: %w", path, err)
	}
	if info.IsDir() {
		return nil, fmt.Errorf("local path %s is a directory, not an image file", path)
	}
	if info.Size() > ocrMaxImageBytes {
		return nil, fmt.Errorf("local image %s has size %d bytes, exceeding the limit of %d bytes (20 MiB)",
			path, info.Size(), ocrMaxImageBytes)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read local image %s: %w", path, err)
	}
	if int64(len(data)) > ocrMaxImageBytes {
		return nil, fmt.Errorf("local image %s has size %d bytes, exceeding the limit of %d bytes (20 MiB)",
			path, len(data), ocrMaxImageBytes)
	}
	return data, nil
}

// ocrDownloadImage downloads the image pointed to by image_url and validates the size.
//
// LimitReader is used to read 1 extra byte to determine "whether it is over the limit", avoiding reading an oversized response into memory first.
func ocrDownloadImage(rawURL string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to build the image download request: %w", err)
	}
	client := &http.Client{Timeout: ocrDownloadTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to download image %s: %w", rawURL, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("failed to download image %s (HTTP %d): %s",
			rawURL, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	data, err := io.ReadAll(io.LimitReader(resp.Body, ocrMaxImageBytes+1))
	if err != nil {
		return nil, fmt.Errorf("failed to read the response for image %s: %w", rawURL, err)
	}
	if int64(len(data)) > ocrMaxImageBytes {
		return nil, fmt.Errorf("image %s exceeds the size limit of %d bytes (20 MiB)", rawURL, ocrMaxImageBytes)
	}
	if len(data) == 0 {
		return nil, fmt.Errorf("image %s download result is empty", rawURL)
	}
	return data, nil
}

// ocrResolveGateway resolves the gateway address to use.
//
// When gateway is explicitly provided, it is used directly; when it is not, it falls back to
// "the first gateway the daemon has authenticated with".
// The fallback relies on the credential provider injected by main.go (see SetBrowserExtCredentialProvider in browser_ext_cred.go);
// here it is implemented through the list function injected by ocrGatewayLister, avoiding the capability package depending back on the auth package.
func ocrResolveGateway(explicit string) (string, error) {
	if explicit != "" {
		return explicit, nil
	}
	gateways := ocrListGateways()
	if len(gateways) == 0 {
		return "", fmt.Errorf("parameter gateway was not specified and the daemon currently has no authenticated gateway; " +
			"please log in on the web page and push the login information first, or pass gateway explicitly")
	}
	return gateways[0], nil
}

// ocrPostJSON POSTs a JSON request body to the gateway and returns the parsed response.
//
// Similar to transferRemotePost in transfer_remote.go, but the error messages are oriented to the OCR scenario,
// and the response body limit is relaxed to 8 MiB for the scale of an OCR result (text + per-line details).
func ocrPostJSON(gateway, apiPath, token string, payload map[string]any) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to serialize the OCR request body: %w", err)
	}
	url := gateway + apiPath
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to build the OCR request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	client := &http.Client{Timeout: ocrHTTPTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request to %s failed: %w", url, err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, fmt.Errorf("failed to read the response for %s: %w", url, err)
	}
	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, fmt.Errorf("failed to parse the response for %s (HTTP %d): %s",
			url, resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if resp.StatusCode != http.StatusOK {
		// On gateway authentication failure (401/403), give a hint closer to the cause.
		if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
			return nil, fmt.Errorf("gateway %s rejected the OCR request (HTTP %d, the Token may have expired): %v",
				gateway, resp.StatusCode, parsed["detail"])
		}
		return nil, fmt.Errorf("the OCR request to gateway %s failed (HTTP %d): %v",
			gateway, resp.StatusCode, parsed["error"])
	}
	return parsed, nil
}

// handleOcrRecognize is the implementation of ocr.recognize.
//
// Flow: parse parameters -> get the gateway and Token -> get the image bytes (read locally / download from URL) ->
// base64 -> POST gateway /api/ocr -> normalize the return.
func handleOcrRecognize(params map[string]any) (any, error) {
	p, err := parseOcrParams(params)
	if err != nil {
		return nil, err
	}
	gateway, err := ocrResolveGateway(p.Gateway)
	if err != nil {
		return nil, err
	}
	token, ok := browserExtToken(gateway)
	if !ok || token == "" {
		return nil, fmt.Errorf("gateway %s has no available credentials and cannot call OCR; please log in on the web page and push the login information first",
			gateway)
	}

	var data []byte
	if p.Image != "" {
		data, err = ocrReadLocalImage(p.Image)
	} else {
		data, err = ocrDownloadImage(p.ImageURL)
	}
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > ocrMaxImageBytes {
		return nil, fmt.Errorf("the image size %d bytes exceeds the limit of %d bytes (20 MiB)",
			len(data), ocrMaxImageBytes)
	}

	filename := ocrNormalizeFilename(p.Filename)
	payload := map[string]any{
		"image_base64": base64.StdEncoding.EncodeToString(data),
		"filename":     filename,
		"backend":      p.Backend,
		"lang":         p.Lang,
		"detail":       p.Detail,
	}
	if p.HasPSM {
		payload["psm"] = p.PSM
	} else {
		// Explicitly pass null: let the gateway's OcrTool use the backend default.
		payload["psm"] = nil
	}

	parsed, err := ocrPostJSON(gateway, "/api/ocr", token, payload)
	if err != nil {
		return nil, err
	}

	// Gateway-side convention: when success=false, the error field gives the reason (such as "no available OCR backend").
	success, _ := parsed["success"].(bool)
	text, _ := parsed["text"].(string)
	backend, _ := parsed["backend"].(string)
	lines, _ := parsed["lines"].([]any)
	ocrErr, _ := parsed["error"].(string)
	if !success {
		if ocrErr == "" {
			ocrErr = "the gateway OCR returned a failure but provided no reason"
		}
		return nil, fmt.Errorf("gateway %s OCR recognition failed: %s", gateway, ocrErr)
	}

	result := map[string]any{
		"success": true,
		"text":    text,
		"backend": backend,
		"gateway": gateway,
		"size":    len(data),
	}
	if lines == nil {
		result["lines"] = []any{}
	} else {
		result["lines"] = lines
	}
	if p.Image != "" {
		result["image"] = p.Image
	} else {
		result["image_url"] = p.ImageURL
	}
	return result, nil
}
