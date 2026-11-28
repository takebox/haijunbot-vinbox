package service

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestServiceNameAndTaskName(t *testing.T) {
	if ServiceName != "haijunbot-daemon.service" {
		t.Errorf("ServiceName = %q, expected haijunbot-daemon.service", ServiceName)
	}
	if TaskName != "HaijunBot-Daemon" {
		t.Errorf("TaskName = %q, expected HaijunBot-Daemon", TaskName)
	}
}

func TestResolveExecPathUsesProvidedPath(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "haijunbot-daemon")
	if err := os.WriteFile(target, []byte("x"), 0o755); err != nil {
		t.Fatalf("failed to prepare the test file: %v", err)
	}
	got, err := ResolveExecPath(Options{ExecPath: target})
	if err != nil {
		t.Fatalf("ResolveExecPath returned an error: %v", err)
	}
	if got != target {
		t.Errorf("ResolveExecPath = %q, expected %q", got, target)
	}
}

func TestResolveExecPathFallsBackToCurrentProcess(t *testing.T) {
	got, err := ResolveExecPath(Options{})
	if err != nil {
		t.Fatalf("ResolveExecPath returned an error: %v", err)
	}
	if !filepath.IsAbs(got) {
		t.Errorf("the fallback path should be absolute, got %q", got)
	}
	if _, err := os.Stat(got); err != nil {
		t.Errorf("the fallback path is not accessible: %v", err)
	}
}

func TestBuildRunArgs(t *testing.T) {
	cases := []struct {
		name string
		opts Options
		want []string
	}{
		{
			name: "listen only",
			opts: Options{Listen: "127.0.0.1:17800"},
			want: []string{"run", "--listen", "127.0.0.1:17800"},
		},
		{
			name: "all arguments",
			opts: Options{Listen: "127.0.0.1:17800", Gateway: "https://hjb-ai.cn", ConfigPath: "/tmp/c.yaml"},
			want: []string{"run", "--listen", "127.0.0.1:17800", "--gateway", "https://hjb-ai.cn", "--config", "/tmp/c.yaml"},
		},
		{
			name: "empty arguments",
			opts: Options{},
			want: []string{"run"},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := BuildRunArgs(c.opts)
			if strings.Join(got, " ") != strings.Join(c.want, " ") {
				t.Errorf("BuildRunArgs = %v, expected %v", got, c.want)
			}
		})
	}
}

func TestNewReturnsPlatformService(t *testing.T) {
	svc := New()
	if svc == nil {
		t.Fatal("New() returned nil")
	}
	_, isUnsupported := svc.(*unsupportedService)
	switch runtime.GOOS {
	case "linux", "windows":
		if isUnsupported {
			t.Errorf("platform %s should not return unsupportedService", runtime.GOOS)
		}
	default:
		if !isUnsupported {
			t.Errorf("platform %s should return unsupportedService", runtime.GOOS)
		}
	}
}

func TestUnsupportedServiceErrors(t *testing.T) {
	s := &unsupportedService{goos: "plan9"}
	if _, err := s.Install(Options{}); err == nil {
		t.Error("Install should return an error")
	}
	if _, err := s.Status(); err == nil {
		t.Error("Status should return an error")
	}
	if _, err := s.Start(); err == nil {
		t.Error("Start should return an error")
	}
}
