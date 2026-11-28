# -*- coding: utf-8 -*-
"""Track installer - supports Git Clone mode only"""

import os
import shutil
import subprocess
import requests
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from abc import ABC, abstractmethod

# Avoid circular imports
if TYPE_CHECKING:
    from haijunbot.haijunbot_agent.rules_manager import RulesManager

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.exception_utils import save_exception
from .sources.base import TrackResult


class IDownloader(ABC):
    """Downloader abstract interface (kept for backward compatibility)"""

    @abstractmethod
    def download(self, url: str) -> str:
        """Download file content"""
        ...


class RequestsDownloader(IDownloader):
    """Downloader implementation based on requests (kept for backward compatibility)"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def download(self, url: str) -> str:
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return ""


class TrackInstaller:
    """
    Track installer (supports Git Clone mode only)

    Dependency injection:
        - rules_manager: used to load newly installed rules
        - downloader: kept for backward compatibility (no longer used)
    """

    def __init__(
        self,
        rules_manager: Optional["RulesManager"] = None,
        downloader: Optional[IDownloader] = None,
        install_dir: Optional[str] = None,
    ):
        """
        Args:
            rules_manager: RulesManager instance (used for hot reloading)
            downloader: Downloader instance (kept for backward compatibility)
            install_dir: Installation directory (optional)
        """
        # Dependency injection
        self.rules_manager = rules_manager
        self.downloader = downloader or RequestsDownloader()

        # Installation directory
        self.install_dir = install_dir or os.path.join(
            get_data_dir(), "rules", "auto_installed_tracks"
        )
        os.makedirs(self.install_dir, exist_ok=True)

    def install(self, track: TrackResult) -> str:
        """
        Install a track (supports Git Clone mode only)

        Clones the entire repository and extracts the subdirectory, preserving all files of the track.
        Falling back to single-file download mode is prohibited.

        Args:
            track: Track result object

        Returns:
            The saved rule file path (the full path of TRACK.md)

        Raises:
            ValueError: Raised when cloning fails or the repository information is incomplete
        """
        # Must contain repo_info information
        repo_info = (
            track._raw_data.get("repo_info")
            if isinstance(track._raw_data, dict)
            else None
        )

        if not repo_info or not repo_info.get("clone_url"):
            raise ValueError(
                f"Track '{track.name}' is missing the required repository information.\n"
                f"repo_info.clone_url must be provided\n"
                f"Current _raw_data: {track._raw_data}"
            )

        # If subdir is empty, try to parse the subdirectory path from repo_url
        if not repo_info.get("subdir"):
            repo_url = (
                track._raw_data.get("repo_url", "")
                if isinstance(track._raw_data, dict)
                else ""
            )
            parsed_subdir = self._parse_subdir_from_repo_url(repo_url)
            if parsed_subdir:
                repo_info["subdir"] = parsed_subdir

        return self._install_via_git_clone(track, repo_info)

    def _parse_subdir_from_repo_url(self, repo_url: str) -> str:
        """Parse the subdirectory path from repo_url.

        Supported formats:
        - https://github.com/owner/repo/tree/main/tracks/de-slopify
        - https://github.com/owner/repo/tree/master/tracks/de-slopify

        Returns:
            The subdirectory path (e.g. "tracks/de-slopify"), or an empty string if parsing fails
        """
        if not repo_url:
            return ""
        # Match the /tree/<branch>/<subdir> format
        marker = "/tree/"
        idx = repo_url.find(marker)
        if idx == -1:
            return ""
        # Skip the /tree/<branch>/ part
        rest = repo_url[idx + len(marker) :]
        parts = rest.split("/", 1)
        if len(parts) < 2:
            return ""
        return parts[1]

    def _install_via_git_clone(self, track: TrackResult, repo_info: dict) -> str:
        """Install the track package via git clone (clone directly into the rules directory, without modifying the original content)"""
        clone_url = repo_info.get("clone_url", "")
        subdir = repo_info.get("subdir", "")

        if not clone_url:
            raise ValueError(f"Invalid repository information: {repo_info}")

        rule_name = self._sanitize_name(track.name)
        target_track_dir = os.path.join(self.install_dir, rule_name)

        # Clean up an existing directory with the same name
        if os.path.exists(target_track_dir):
            shutil.rmtree(target_track_dir)

        # Parse the repository name (extract from clone_url)
        repo_name = clone_url.rstrip("/").split("/")[-1].replace(".git", "")
        repo_dir = os.path.join(target_track_dir, repo_name)

        # git clone --depth 1 into <track_name>/<repo_name>/
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, repo_dir],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            # Clean up leftover directories when clone fails
            if os.path.exists(target_track_dir):
                shutil.rmtree(target_track_dir)
            stderr = (result.stderr or "").strip()
            # Authentication-type errors usually mean the repository does not exist/is private/requires auth,
            # rather than a network problem. Give a clearer hint to avoid the misleading "could not read Username"
            auth_hints = (
                "could not read Username",
                "Authentication failed",
                "Invalid username or token",
                "could not read Password",
                "Repository not found",
                "remote: Repository not found",
            )
            if any(h in stderr for h in auth_hints):
                raise ValueError(
                    f"Git clone failed: repository '{clone_url}' is inaccessible (it may not exist, "
                    f"have been deleted, be private, or require authentication). Please confirm that this track repository is still publicly accessible.\nOriginal error: {stderr}"
                )
            raise ValueError(f"Git clone failed: {stderr}")

        # Locate TRACK.md in the track subdirectory
        track_md_path = (
            os.path.join(repo_dir, subdir, "TRACK.md")
            if subdir
            else os.path.join(repo_dir, "TRACK.md")
        )

        if not os.path.exists(track_md_path):
            # Try the path without the tracks prefix
            alt_subdir = (
                subdir.replace("tracks/", "", 1)
                if subdir.startswith("tracks/")
                else f"tracks/{subdir}"
            )
            alt_track_md_path = os.path.join(repo_dir, alt_subdir, "TRACK.md")

            if os.path.exists(alt_track_md_path):
                track_md_path = alt_track_md_path
            else:
                # Clone succeeded but TRACK.md could not be found; clean up and raise
                shutil.rmtree(target_track_dir)
                raise ValueError(f"TRACK.md was not found in subdirectory {subdir}")

        # Generate the track.md index file (containing description + track_path)
        self._generate_track_md_index(target_track_dir, track, repo_name)

        # Hot reload (do not modify TRACK.md; keep the original content)
        if self.rules_manager:
            try:
                load_method = getattr(self.rules_manager, "load_rule_file", None)
                if load_method:
                    load_method(track_md_path)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.track_discovery.installer",
                    function="_install_via_git_clone",
                )
                pass

        return track_md_path

    def _generate_track_md_index(
        self, target_track_dir: str, track: TrackResult, repo_name: str
    ) -> None:
        """Generate the track.md index file

        Generates track.md at the root of the track directory, containing description and track_path.
        track_path uses the {{ rule_file_dir }} template variable to point to the repository subdirectory,
        so that when rules_manager scans it, it stops traversing sublevels upon encountering track.md.

        Args:
            target_track_dir: track installation directory
            track: Track result object
            repo_name: repository subdirectory name
        """
        try:
            # Use the template variable {{ rule_file_dir }} to point to the repository subdirectory
            track_path_ref = "{{ rule_file_dir }}/" + repo_name

            index_content = f"""---
name: {track.name}
description: {track.description or track.name}
---

# {track.name}

{track.description or ""}

track_path: {track_path_ref}
"""

            index_path = os.path.join(target_track_dir, "track.md")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(index_content)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.track_discovery.installer",
                function="_generate_track_md_index",
            )

    def _add_source_header(self, content: str, track: TrackResult) -> str:
        """Prepend a source comment to the original content"""
        header = f"""<!--
  Automatically installed Track
  Source: {track.platform}
  Original link: {track.source_url}
  Installation time: {datetime.now().isoformat()}
  Author: {track.author or "Unknown"}
  Tags: {", ".join(track.tags) if track.tags else "None"}
-->

"""
        return header + content

    def _sanitize_name(self, name: str) -> str:
        """Sanitize the file name"""
        return (
            name.replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "_")
            .replace(":", "-")
        )
