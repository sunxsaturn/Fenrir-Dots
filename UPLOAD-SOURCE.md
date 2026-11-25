# One-time repository bootstrap

The source publisher needs one source archive upload for this repository. This is a one-time step; the GitHub Actions workflow expands it into normal tracked files and removes the archive.

1. Download the matching Fenrir source archive from the ChatGPT conversation.
2. Open this repository on GitHub.
3. Select **Add file → Upload files**.
4. Upload the archive at the repository root without changing its filename:
   - `fenrir-arch-source-0.3.0.tar.gz` for Fenrir-Arch
   - `fenrir-dots-source-0.3.0.tar.gz` for Fenrir-Dots
5. Select **Commit changes** on the `main` branch.
6. Open **Actions** and confirm **Expand Fenrir source archive** completes successfully.

The workflow extracts the source tree, commits its files, and removes the uploaded archive. The final repository contains ordinary files and folders; the archive is not kept in the repository.

After both repositories are populated, the Arch installer can be started with:

```bash
git clone --depth=1 https://github.com/sunxsaturn/Fenrir-Arch.git ~/Fenrir && cd ~/Fenrir && ./install.sh
```
