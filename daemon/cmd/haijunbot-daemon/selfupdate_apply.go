package main

import (
	"flag"
	"fmt"
	"log"
	"time"

	"haijunbot-daemon/internal/selfupdate"
)

// cmdSelfUpdateApply is the auto-update helper subcommand: after the parent process (the old daemon) exits,
// it replaces the target file at --dst with the new executable at --src, and restarts the service as needed.
//
// Why a separate process is needed: Windows does not allow overwriting/renaming a running exe. When the replacement fails, the parent process
// starts this helper (see SpawnApplyHelper in apply_windows.go), then the parent process exits;
// this process waits until the target file is no longer in use, then completes the replacement.
//
// Arguments:
//
//	--src    path to the new version's executable (the helper itself is started from that copy)
//	--dst    the final path to replace (e.g. ~/.haijunbot/bin/haijunbot-daemon.exe)
//	--restart whether to restart the service after a successful replacement
//
// Note: this subcommand is actually used only on Windows; on other platforms the implementation is kept only for cross-platform compilation,
// and since replacing a running file on Linux needs no helper, it will not be triggered.
func cmdSelfUpdateApply(args []string) error {
	fs := flag.NewFlagSet("self-update-apply", flag.ContinueOnError)
	srcFlag := fs.String("src", "", "path to the new version's executable")
	dstFlag := fs.String("dst", "", "target path to replace")
	restartFlag := fs.Bool("restart", false, "restart the service after a successful replacement")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *srcFlag == "" || *dstFlag == "" {
		return fmt.Errorf("self-update-apply requires --src and --dst")
	}

	// Wait for the parent process to exit and release the target file; after the timeout it still attempts the replacement (it may already be writable).
	if err := waitForReplaceTarget(*dstFlag, 60*time.Second); err != nil {
		log.Printf("[selfupdate-helper] Timed out waiting for the target file to be replaceable; still attempting replacement: %v", err)
	}

	if err := selfupdate.Apply(*srcFlag, *dstFlag); err != nil {
		return fmt.Errorf("helper failed to replace executable: %w", err)
	}
	log.Printf("[selfupdate-helper] Replaced %s", *dstFlag)

	if *restartFlag {
		if err := restartServiceForHelper(); err != nil {
			// A restart failure is not fatal: the file is already the new version, and the user can restart manually.
			log.Printf("[selfupdate-helper] Failed to restart service (manual restart possible): %v", err)
		}
	}
	return nil
}
