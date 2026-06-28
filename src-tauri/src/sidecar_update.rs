//! Sync bundled Sidecar binary into app data dir with atomic replace (Phase 4 updater flow).

use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};
use tauri::path::BaseDirectory;

const SIDECAR_NAME: &str = "agent-api";

pub fn install_dir(data_dir: &Path) -> PathBuf {
    data_dir.join("sidecar")
}

pub fn installed_binary(data_dir: &Path) -> PathBuf {
    let ext = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };
    install_dir(data_dir).join(format!("{SIDECAR_NAME}{ext}"))
}

fn version_file(data_dir: &Path) -> PathBuf {
    install_dir(data_dir).join("version.txt")
}

fn target_triple() -> &'static str {
    if cfg!(target_os = "windows") {
        if cfg!(target_arch = "aarch64") {
            "aarch64-pc-windows-msvc"
        } else {
            "x86_64-pc-windows-msvc"
        }
    } else if cfg!(target_os = "macos") {
        if cfg!(target_arch = "aarch64") {
            "aarch64-apple-darwin"
        } else {
            "x86_64-apple-darwin"
        }
    } else if cfg!(target_arch = "aarch64") {
        "aarch64-unknown-linux-gnu"
    } else {
        "x86_64-unknown-linux-gnu"
    }
}

fn bundled_binary(app: &AppHandle) -> Result<PathBuf, String> {
    let ext = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };
    let rel = format!("binaries/{SIDECAR_NAME}-{}{ext}", target_triple());
    app.path()
        .resolve(rel, BaseDirectory::Resource)
        .map_err(|e| format!("Resolve bundled sidecar: {e}"))
}

fn atomic_copy(src: &Path, dest: &Path) -> Result<(), String> {
    let parent = dest
        .parent()
        .ok_or_else(|| "Invalid sidecar dest path".to_string())?;
    std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let tmp = dest.with_extension("new");
    std::fs::copy(src, &tmp).map_err(|e| format!("Copy sidecar: {e}"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o755));
    }
    if dest.exists() {
        std::fs::remove_file(dest).map_err(|e| format!("Remove old sidecar: {e}"))?;
    }
    std::fs::rename(&tmp, dest).map_err(|e| format!("Activate sidecar: {e}"))?;
    Ok(())
}

/// Copy bundled Sidecar into app data when app version changes. Returns true if updated.
pub fn sync_from_bundle(app: &AppHandle, data_dir: &Path) -> Result<bool, String> {
    let expected = env!("CARGO_PKG_VERSION");
    let dest = installed_binary(data_dir);
    let ver_path = version_file(data_dir);

    if dest.is_file() {
        if let Ok(current) = std::fs::read_to_string(&ver_path) {
            if current.trim() == expected {
                return Ok(false);
            }
        }
    }

    let bundled = bundled_binary(app)?;
    if !bundled.is_file() {
        log::warn!(
            "Bundled sidecar missing at {} — using shell sidecar",
            bundled.display()
        );
        return Ok(false);
    }

    log::info!(
        "Updating Sidecar to v{expected} (from {})",
        bundled.display()
    );
    atomic_copy(&bundled, &dest)?;
    std::fs::write(&ver_path, expected).map_err(|e| e.to_string())?;
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn installed_binary_name() {
        let p = installed_binary(Path::new("/tmp/data"));
        assert!(p.to_string_lossy().contains("agent-api"));
    }
}
