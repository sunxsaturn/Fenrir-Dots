# Fenrir public wallpaper library

**Population status (2026-11-27): closed.** The existing 1,871 published images in three volumes remain active for desktop synchronization. No more acquisitions, image-count balancing or new volumes are scheduled. There is no fixed image target.

This feature synchronizes the public, multi-repository wallpaper library into one local Fenrir rotation directory. It is separate from the private Wallpaper Catalog workflow.

**Fresh installation:** Fenrir-Arch invokes this exact Dots sync command automatically after deploying the pinned dotfiles. The documented one-command installer downloads every manifest-listed image from all active volumes. No separate wallpaper download command is required after installation.

## Commands

The following commands are available for existing installations, audits and recovery. They are not an additional step in a fresh system installation.

Run the read-only registry and manifest audit (no image downloads and no local folder scan):

```bash
fenrir-wallpaper audit-library --json
```

Preview the registry and all active manifests without creating or changing files:

```bash
fenrir-wallpaper sync-library --dry-run
```

Synchronize all active volumes:

```bash
fenrir-wallpaper sync-library
```

Process a small number of new images first:

```bash
fenrir-wallpaper sync-library --limit 10
```

Use `--json` with any command for a machine-readable report. The command uses the existing `wallpaper.directory` setting (default: `~/Pictures/Wallpapers`). The dry-run report includes destination and resumable-cache free space. A real sync refuses to start when either filesystem lacks the required capacity.

## Use Fenrir Settings and Doctor

- **Fenrir Settings → Wallpapers → Public multi-volume wallpaper library** provides a read-only preview in a terminal and a separate, confirmation-gated synchronization action.
- **Fenrir Doctor → Wallpapers → Public multi-volume library** audits manifest SHA declarations, uniqueness, categories, dimensions, metadata/rights gaps, palette metadata and repository storage headroom. The audit never downloads image bytes or inspects the local folder. Preview is read-only; synchronization requires a separate explicit confirmation.
- The public mirror controls are independent of the private Catalog's accepted-wallpaper sync and metadata discovery scheduler. Public image population is closed; all current volumes remain active for sync.

## How it works

1. Fetches the fixed public registry at `Fenrir-Wallpapers/manifest/volumes.json`.
2. Validates the registry identity, active volume entries, repository names, branches and manifest paths.
3. Fetches and validates every active volume manifest before starting any image transfer.
4. Deduplicates image records globally by SHA-256.
5. Downloads the committed image bytes from the matching `raw.githubusercontent.com` repository path.
6. Resumes interrupted transfers using HTTP Range requests where supported.
7. Verifies exact byte size, SHA-256, decoded image format, landscape dimensions and the same palette policy used by rotation.
8. Installs each image atomically without replacing existing files.
9. Writes public-source provenance to `.fenrir-public-library-attribution.json`, separate from the private Catalog attribution sidecar.
10. Refreshes the local wallpaper index after successful transfers.

The local directory structure is `<wallpaper.directory>/<category>/<sha256>.<extension>`, so the existing recursive wallpaper scanner can use the combined library without hard-coded volume names.

## Safety and behavior

- Only volumes marked `active: true` in the canonical registry are synchronized. Every current volume is marked `acquisition_enabled: false` and `status: closed`; acquisition state does not affect local download eligibility.
- Only committed files listed in a volume's validated manifest are fetched. The desktop does not query Wikimedia or other providers.
- Image URLs are constructed from the registered GitHub repository, branch and manifest path; manifest-supplied arbitrary download URLs are not followed.
- Existing local files are never overwritten or deleted.
- Global duplicate detection uses content hashes, not titles or filenames alone.
- A separate process lock prevents overlapping library sync commands. The public population workflows are closed; sync transfers already-published manifest entries only.
- Partial downloads are kept in the Fenrir state directory and resumed on the next invocation.
- The private Catalog database, quarantine and `fenrir-catalog sync-catalog` path are not read or modified.
- `/mnt/storage` destinations and paths containing symbolic links are rejected.
- One failed image is reported without discarding other successfully synchronized images. The command exits nonzero when any image fails.
- Use `--dry-run` to review the entire existing public library before synchronization. `--limit` remains a technical transfer-batch cap, not a collection-size goal.

The complete 1,871-image synchronization may require substantial disk space and network traffic. The one-command installer computes the exact missing-image byte total and checks destination/cache capacity before downloading; it stops before transfers if space is insufficient. Interrupted downloads remain resumable.

## Attribution

The hidden sidecar `.fenrir-public-library-attribution.json` preserves each synchronized image's repository and volume, creator, credit, source page, attribution, license identifier and license URL. It is distinct from `fenrir-catalog-attribution.json`, which belongs to the private Catalog's locally accepted collection.

The public mirror's documented license metadata and provider terms remain the responsibility of the publisher. Automated synchronization preserves evidence; it does not grant additional rights or authorize redistribution.

## Troubleshooting

- **Registry or manifest rejected:** check the hub registry and manifests in the public wallpaper repositories. The command validates all active manifests before it transfers images.
- **Transfer interrupted:** run the same command again. A saved partial file is resumed when the server supports byte ranges.
- **Existing file conflict:** the command stops overwriting that path and reports the conflict. Move or rename the conflicting file yourself only after reviewing it.
- **Image rejected:** the downloaded bytes did not pass the desktop's decoded format, minimum landscape resolution or palette checks. The invalid partial is discarded.
- **Another sync is running:** allow the active command to finish before starting another.
- **New images do not appear immediately:** the local validation index is refreshed after successful sync; wallpaper rotation uses them on its next scheduled or manual cycle.
