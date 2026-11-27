"""Fenrir Doctor: GTK4 dashboard for diagnostics and rights-aware wallpaper intelligence."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

APP_ID = "org.fenrir.desktop.doctor"
PROVIDER_TERMS_URLS = {
    "cleveland": "https://www.clevelandart.org/terms-and-conditions",
    "met": "https://www.metmuseum.org/about-the-met/policies-and-documents/open-access-policy",
    "wikimedia": "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
    "aic": "https://www.artic.edu/open-access/open-access-images",
    "openverse": "https://docs.openverse.org/terms_of_service",
    "smk": "https://www.smk.dk/en/article/free-download-of-images/",
}


def command(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, (result.stdout or result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def catalog_json(*args: str, timeout: int = 60):
    code, output = command(["fenrir-catalog", *args], timeout=timeout)
    if code:
        raise RuntimeError(output or "Fenrir Catalog command failed")
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Fenrir Catalog returned invalid JSON") from exc


class FenrirDoctor(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None
        self.candidates: list[dict] = []
        self.selected: dict | None = None
        self.status_label = None
        self.inventory_label = None
        self.campaign_label = None
        self.candidate_list = None
        self.detail_label = None
        self.rationale = None
        self.action_label = None
        self.open_button = None
        self.terms_button = None
        self.preview_button = None
        self.source_reviewed = None
        self.terms_reviewed = None
        self.publish_gallery_button = None
        self.publishing = False
        self.review_button = None
        self.acquire_button = None
        self.accept_button = None
        self.publish_button = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("Fenrir Doctor")
        window.set_default_size(1040, 760)
        self.window = window

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(20)
        root.set_margin_bottom(20)
        root.set_margin_start(22)
        root.set_margin_end(22)
        window.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label="FENRIR DOCTOR")
        title.add_css_class("title-1")
        title.set_xalign(0)
        header.append(title)
        header.append(Gtk.Box(hexpand=True))
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.append(refresh)
        root.append(header)

        intro = Gtk.Label(
            label="System health and the private, rights-aware 5,000-image wallpaper population."
        )
        intro.set_xalign(0)
        intro.add_css_class("dim-label")
        root.append(intro)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        status_box.add_css_class("card")
        status_box.set_margin_bottom(4)
        self.status_label = Gtk.Label(label="Checking Fenrir services…")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        status_box.append(self.status_label)
        self.inventory_label = Gtk.Label(label="Wallpaper inventory: loading…")
        self.inventory_label.set_xalign(0)
        self.inventory_label.set_wrap(True)
        status_box.append(self.inventory_label)
        self.campaign_label = Gtk.Label(label="Discovery campaigns: loading…")
        self.campaign_label.set_xalign(0)
        self.campaign_label.set_wrap(True)
        status_box.append(self.campaign_label)
        root.append(status_box)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        run_slice = Gtk.Button(label="Run next discovery slice")
        run_slice.connect("clicked", self.run_slice)
        toolbar.append(run_slice)
        open_diagnostics = Gtk.Button(label="System diagnostics")
        open_diagnostics.connect("clicked", self.show_diagnostics)
        toolbar.append(open_diagnostics)
        self.publish_gallery_button = Gtk.Button(label="Publish complete 5,000-image gallery")
        self.publish_gallery_button.connect("clicked", self.confirm_publish_gallery)
        toolbar.append(self.publish_gallery_button)
        root.append(toolbar)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        root.append(paned)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_size_request(420, -1)
        left.append(Gtk.Label(label="DISCOVERED CANDIDATES"))
        self.candidate_list = Gtk.ListBox()
        self.candidate_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.candidate_list.connect("row-selected", self.on_candidate_selected)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.candidate_list)
        scroll.set_vexpand(True)
        left.append(scroll)
        paned.set_start_child(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_margin_start(16)
        right.append(Gtk.Label(label="SELECTED CANDIDATE"))
        self.detail_label = Gtk.Label(label="Select an image candidate to inspect its source and status.")
        self.detail_label.set_xalign(0)
        self.detail_label.set_yalign(0)
        self.detail_label.set_wrap(True)
        self.detail_label.set_selectable(True)
        right.append(self.detail_label)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.open_button = Gtk.Button(label="Open source page")
        self.open_button.connect("clicked", lambda *_: self.open_source())
        self.terms_button = Gtk.Button(label="Open provider terms")
        self.terms_button.connect("clicked", lambda *_: self.open_provider_terms())
        self.preview_button = Gtk.Button(label="Preview quarantine file")
        self.preview_button.connect("clicked", lambda *_: self.preview_asset())
        buttons.append(self.open_button)
        buttons.append(self.terms_button)
        buttons.append(self.preview_button)
        right.append(buttons)

        right.append(Gtk.Label(label="Human review rationale (required for decisions)"))
        self.rationale = Gtk.Entry()
        self.rationale.set_placeholder_text("Explain the source, license and decision you reviewed…")
        right.append(self.rationale)
        self.source_reviewed = Gtk.CheckButton(label="I inspected the original image page and its item-specific license.")
        self.source_reviewed.connect("toggled", lambda *_: self._button_states())
        right.append(self.source_reviewed)
        self.terms_reviewed = Gtk.CheckButton(label="I reviewed the provider's current terms for this use.")
        self.terms_reviewed.connect("toggled", lambda *_: self._button_states())
        right.append(self.terms_reviewed)
        right.append(Gtk.Label(label="Original media-host terms URL (required for Openverse)"))
        self.source_terms_url = Gtk.Entry()
        self.source_terms_url.set_placeholder_text("https://original-host.example/terms")
        self.source_terms_url.connect("changed", lambda *_: self._button_states())
        self.source_terms_url.set_sensitive(False)
        right.append(self.source_terms_url)

        action_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        self.review_button = Gtk.Button(label="Approve rights + source terms")
        self.review_button.connect("clicked", lambda *_: self.review_rights())
        self.acquire_button = Gtk.Button(label="Authorize + acquire")
        self.acquire_button.connect("clicked", lambda *_: self.acquire())
        self.accept_button = Gtk.Button(label="Accept validated image")
        self.accept_button.connect("clicked", lambda *_: self.accept())
        self.publish_button = Gtk.Button(label="Approve public publication")
        self.publish_button.connect("clicked", lambda *_: self.approve_publication())
        action_grid.attach(self.review_button, 0, 0, 1, 1)
        action_grid.attach(self.acquire_button, 1, 0, 1, 1)
        action_grid.attach(self.accept_button, 0, 1, 1, 1)
        action_grid.attach(self.publish_button, 1, 1, 1, 1)
        right.append(action_grid)

        self.action_label = Gtk.Label(label="Each rights, acquisition, acceptance and publication step is recorded separately.")
        self.action_label.set_xalign(0)
        self.action_label.set_wrap(True)
        right.append(self.action_label)
        paned.set_end_child(right)
        paned.set_position(430)

        window.present()
        self.refresh()

    def _user(self) -> str:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or "local-reviewer"

    def _rationale(self) -> str:
        value = self.rationale.get_text().strip()
        if len(value) < 12:
            raise RuntimeError("Enter a meaningful review rationale (at least 12 characters).")
        return value

    def _selected_id(self) -> str:
        if not self.selected:
            raise RuntimeError("Select a candidate first.")
        return str(self.selected["asset_id"])

    def _set_action(self, message: str, error: bool = False):
        self.action_label.set_text(message)
        self.action_label.remove_css_class("error")
        if error:
            self.action_label.add_css_class("error")

    def _button_states(self):
        item = self.selected or {}
        state = item.get("state")
        self.open_button.set_sensitive(bool(item.get("source_page")))
        provider = item.get("provider")
        is_openverse = provider == "openverse"
        self.terms_button.set_sensitive(provider in PROVIDER_TERMS_URLS)
        self.terms_button.set_label(
            "Open supplied source-host terms" if is_openverse and self.source_terms_url.get_text().strip()
            else ("Open Openverse API terms" if is_openverse else "Open provider terms")
        )
        self.source_terms_url.set_sensitive(is_openverse)
        source_terms_url = self.source_terms_url.get_text().strip()
        source_terms_url_valid = (
            not is_openverse or source_terms_url.startswith("https://")
        )
        self.preview_button.set_sensitive(state in {"quarantined", "duplicate-review", "accepted"} and bool(item.get("validated_asset")))
        self.review_button.set_sensitive(
            state in {"discovered", "rights-review", "deferred"}
            and self.source_reviewed.get_active()
            and self.terms_reviewed.get_active()
            and source_terms_url_valid
        )
        self.acquire_button.set_sensitive(state == "rights-review")
        self.accept_button.set_sensitive(state == "quarantined")
        self.publish_button.set_sensitive(state == "accepted")

    def refresh(self):
        if not shutil.which("fenrir-catalog"):
            self.status_label.set_text("Private Catalog is not installed or ~/.local/bin is not on PATH.")
            return
        try:
            population = catalog_json("population-status")
            inventory = catalog_json("inventory")
            published = catalog_json("publication-status")
            self.candidates = catalog_json("candidates", "--limit", "250")
            counts = population.get("campaigns", {})
            self.status_label.set_text(
                "Fenrir Doctor is running. Discovery is metadata-only; no image bytes are downloaded by campaigns."
            )
            category_text = ", ".join(
                f"{key}: {value}" for key, value in sorted(inventory.get("by_category", {}).items())
            ) or "No candidates discovered yet."
            self.inventory_label.set_text(
                f"Candidate metadata: {inventory.get('candidates', 0)}. "
                f"Public target: 5,000 unique images. "
                f"Published: {published.get('published_records', 0)}; "
                f"remaining: {published.get('remaining', 5000)}. "
                f"Legacy exclusion set: 1,871 hashes.\n{category_text}"
            )
            self.campaign_label.set_text(
                "Campaigns: "
                + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
                + f". Pending scheduler turns: {counts.get('planned', 0) + counts.get('paused', 0)}."
            )
            self._populate_candidates()
        except Exception as exc:
            self.status_label.set_text(f"Catalog status unavailable: {exc}")

    def _populate_candidates(self):
        child = self.candidate_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.candidate_list.remove(child)
            child = next_child
        self.selected = None
        for item in self.candidates:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_top(7)
            box.set_margin_bottom(7)
            box.set_margin_start(8)
            box.set_margin_end(8)
            headline = Gtk.Label(label=item.get("title", "Untitled"))
            headline.set_xalign(0)
            headline.add_css_class("heading")
            box.append(headline)
            detail = Gtk.Label(
                label=f"{item.get('category_id')} · {item.get('provider')} · "
                      f"{item.get('license_identifier')} · {item.get('state')}"
            )
            detail.set_xalign(0)
            detail.add_css_class("dim-label")
            box.append(detail)
            row.set_child(box)
            self.candidate_list.append(row)
        self._button_states()

    def on_candidate_selected(self, _list, row):
        if row is None:
            self.selected = None
            self._button_states()
            return
        index = row.get_index()
        if not 0 <= index < len(self.candidates):
            return
        self.selected = self.candidates[index]
        self.source_reviewed.set_active(False)
        self.terms_reviewed.set_active(False)
        self.source_terms_url.set_text("")
        self.terms_reviewed.set_label(
            "I reviewed the original media host's current terms for this use."
            if self.selected.get("provider") == "openverse"
            else "I reviewed the provider's current terms for this use."
        )
        self._button_states()
        try:
            detail = catalog_json("candidate-show", self.selected["asset_id"])
            self.selected = {**self.selected, **detail}
            evidence = detail.get("rights_evidence", [])
            evidence_text = "\n".join(
                f"  {entry['evidence_type']}: {entry['decision']} — {entry['reviewer']}"
                for entry in evidence
            ) or "  No human rights evidence recorded."
            validated = detail.get("validated_asset")
            validated_text = (
                f"SHA-256: {validated['sha256']}\nQuarantine: {validated['quarantine_path']}"
                if validated else "No validated quarantine file."
            )
            self.detail_label.set_text(
                f"{detail.get('title')}\n\n"
                f"Category: {detail.get('category_id')}\nProvider: {detail.get('provider')}\n"
                f"Creator: {detail.get('creator')}\nLicense: {detail.get('license_identifier')}\n"
                f"Declared dimensions: {detail.get('declared_width')} × {detail.get('declared_height')}\n"
                f"Source page: {detail.get('source_page')}\n"
                f"Image URL host: {detail.get('image_host')}\n"
                f"State: {detail.get('state')}\n\nRights evidence:\n{evidence_text}\n\n{validated_text}"
            )
        except Exception as exc:
            self.detail_label.set_text(str(exc))
        self._button_states()

    def open_source(self):
        if not self.selected:
            return
        url = self.selected.get("source_page")
        if url:
            subprocess.Popen(["xdg-open", url])

    def open_provider_terms(self):
        provider = (self.selected or {}).get("provider")
        supplied = self.source_terms_url.get_text().strip()
        url = supplied if provider == "openverse" and supplied.startswith("https://") else PROVIDER_TERMS_URLS.get(provider)
        if url:
            subprocess.Popen(["xdg-open", url])

    def preview_asset(self):
        validated = (self.selected or {}).get("validated_asset")
        path = validated.get("quarantine_path") if validated else None
        if path and Path(path).is_file():
            subprocess.Popen(["xdg-open", path])

    def _run_action(self, args: list[str]):
        code, output = command(["fenrir-catalog", *args], timeout=300)
        if code:
            raise RuntimeError(output or "Fenrir Catalog action failed")
        self._set_action(output or "Action completed.")
        self.refresh()

    def review_rights(self):
        try:
            if not self.source_reviewed.get_active() or not self.terms_reviewed.get_active():
                raise RuntimeError("Open and inspect both the original item and official provider terms before approving.")
            asset_id, rationale = self._selected_id(), self._rationale()
            args = [
                "rights-review", asset_id, "--reviewer", self._user(),
                "--license-decision", "approved", "--terms-decision", "approved",
                "--rationale", rationale,
            ]
            if (self.selected or {}).get("provider") == "openverse":
                source_terms_url = self.source_terms_url.get_text().strip()
                if not source_terms_url.startswith("https://"):
                    raise RuntimeError("Enter the original media host's HTTPS terms URL before reviewing Openverse rights.")
                args.extend(["--terms-evidence-url", source_terms_url])
            self._run_action(args)
        except Exception as exc:
            self._set_action(str(exc), True)

    def acquire(self):
        try:
            asset_id, rationale = self._selected_id(), self._rationale()
            self._run_action([
                "authorize", asset_id, "--reviewer", self._user(),
                "--rationale", rationale, "--expires-hours", "24",
            ])
            self._run_action(["acquire", asset_id])
        except Exception as exc:
            self._set_action(str(exc), True)

    def accept(self):
        try:
            asset_id, rationale = self._selected_id(), self._rationale()
            self._run_action([
                "accept", asset_id, "--decision", "accept",
                "--reviewer", self._user(), "--rationale", rationale,
            ])
        except Exception as exc:
            self._set_action(str(exc), True)

    def approve_publication(self):
        try:
            asset_id, rationale = self._selected_id(), self._rationale()
            self._run_action([
                "publication-approve", asset_id,
                "--reviewer", self._user(), "--rationale", rationale,
            ])
        except Exception as exc:
            self._set_action(str(exc), True)

    def run_slice(self, *_args):
        try:
            self._run_action(["campaign-run-next"])
        except Exception as exc:
            self._set_action(str(exc), True)

    def confirm_publish_gallery(self, *_args):
        dialog = Gtk.Dialog(
            title="Publish the complete public wallpaper library",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Publish 5,000 images", Gtk.ResponseType.ACCEPT)
        label = Gtk.Label(
            label=(
                "This publishes only images that have passed rights review, acquisition, "
                "technical validation, human acceptance and separate public-publication approval. "
                "It may create additional public image-only repositories. The hub is activated "
                "only after every volume has been pushed successfully."
            )
        )
        label.set_wrap(True)
        label.set_margin_top(18)
        label.set_margin_bottom(18)
        label.set_margin_start(18)
        label.set_margin_end(18)
        dialog.get_content_area().append(label)
        dialog.connect("response", self._publish_response)
        dialog.present()

    def _publish_response(self, dialog, response):
        dialog.close()
        if response != Gtk.ResponseType.ACCEPT or self.publishing:
            return
        self.publishing = True
        self.publish_gallery_button.set_sensitive(False)
        self._set_action("Validating all 5,000 approved images and publishing image-only volumes…")
        threading.Thread(target=self._publish_worker, daemon=True).start()

    def _publish_worker(self):
        code, output = command(
            ["fenrir-catalog", "publish-public", "--reviewer", self._user()],
            timeout=6 * 60 * 60,
        )
        GLib.idle_add(self._publish_complete, code, output)

    def _publish_complete(self, code: int, output: str):
        self.publishing = False
        self.publish_gallery_button.set_sensitive(True)
        self._set_action(
            output or ("Public gallery publication completed." if code == 0 else "Public gallery publication failed."),
            code != 0,
        )
        self.refresh()
        return GLib.SOURCE_REMOVE

    def show_diagnostics(self, *_args):
        lines = []
        for label, args in (
            ("Hyprland", ["hyprctl", "version"]),
            ("GPU renderer", ["glxinfo", "-B"]),
            ("Ollama models", ["ollama", "ps"]),
            ("NetworkManager", ["systemctl", "is-active", "NetworkManager"]),
            ("SDDM", ["systemctl", "is-enabled", "sddm"]),
            ("Bluetooth", ["systemctl", "is-active", "bluetooth"]),
            ("Wake-on-LAN", ["systemctl", "is-enabled", "fenrir-wol"]),
        ):
            code, output = command(args, timeout=15)
            lines.append(f"{label}: {output or ('not available' if code else 'OK')}")
        dialog = Gtk.Dialog(title="Fenrir System Diagnostics", transient_for=self.window, modal=True)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        text = Gtk.Label(label="\n\n".join(lines))
        text.set_xalign(0)
        text.set_selectable(True)
        text.set_margin_top(16)
        text.set_margin_bottom(16)
        text.set_margin_start(16)
        text.set_margin_end(16)
        dialog.get_content_area().append(text)
        dialog.connect("response", lambda widget, _response: widget.close())
        dialog.present()


def main() -> int:
    if not shutil.which("fenrir-catalog"):
        print("Fenrir Doctor requires the private Fenrir Wallpaper Catalog.", file=sys.stderr)
        return 2
    application = FenrirDoctor()
    return application.run([])


if __name__ == "__main__":
    raise SystemExit(main())


def control_center_main() -> int:
    """Open Fenrir Doctor's desktop appearance and system control center."""
    return main()
