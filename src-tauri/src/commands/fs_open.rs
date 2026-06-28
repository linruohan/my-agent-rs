use std::path::{Path, PathBuf};
use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

#[derive(serde::Serialize)]
pub struct FileReadResult {
    pub name: String,
    pub content: String,
    pub is_binary: bool,
    pub mime_type: Option<String>,
}

fn mime_from_ext(ext: &str) -> Option<&'static str> {
    match ext {
        "png" => Some("image/png"),
        "jpg" | "jpeg" => Some("image/jpeg"),
        "gif" => Some("image/gif"),
        "webp" => Some("image/webp"),
        "pdf" => Some("application/pdf"),
        _ => None,
    }
}

fn is_binary_ext(ext: &str) -> bool {
    matches!(
        ext,
        "png" | "jpg" | "jpeg" | "gif" | "webp" | "pdf" | "zip" | "doc" | "docx"
    )
}

/// 读取本地文件内容（文本或 base64）
#[tauri::command]
pub fn read_local_file(path: String) -> Result<FileReadResult, String> {
    let p = Path::new(path.trim());
    if !p.exists() {
        return Err(format!("文件不存在: {}", p.display()));
    }
    if !p.is_file() {
        return Err(format!("不是文件: {}", p.display()));
    }

    let name = p
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("file")
        .to_string();
    let ext = p
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    let bytes = std::fs::read(p).map_err(|e| e.to_string())?;

    if is_binary_ext(&ext) {
        use base64::Engine;
        Ok(FileReadResult {
            name,
            content: base64::engine::general_purpose::STANDARD.encode(&bytes),
            is_binary: true,
            mime_type: mime_from_ext(&ext).map(str::to_string),
        })
    } else {
        Ok(FileReadResult {
            name,
            content: String::from_utf8_lossy(&bytes).into_owned(),
            is_binary: false,
            mime_type: None,
        })
    }
}

fn collect_dir_entries(dir: &Path, base: &Path, out: &mut Vec<String>) -> Result<(), String> {
    for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        let rel = path
            .strip_prefix(base)
            .unwrap_or(&path)
            .to_string_lossy()
            .replace('\\', "/");
        if path.is_dir() {
            out.push(format!("{rel}/"));
            collect_dir_entries(&path, base, out)?;
        } else {
            out.push(rel);
        }
    }
    Ok(())
}

/// 递归列出文件夹内相对路径
#[tauri::command]
pub fn list_directory(path: String) -> Result<Vec<String>, String> {
    let p = PathBuf::from(path.trim());
    if !p.exists() {
        return Err(format!("路径不存在: {}", p.display()));
    }
    if !p.is_dir() {
        return Err(format!("不是文件夹: {}", p.display()));
    }
    let mut entries = Vec::new();
    collect_dir_entries(&p, &p, &mut entries)?;
    entries.sort();
    Ok(entries)
}

/// 用系统默认程序打开文件夹（工作区）
#[tauri::command]
pub fn open_workspace_folder(app: AppHandle, path: String) -> Result<(), String> {
    let trimmed = path.trim();
    if trimmed.is_empty() {
        return Err("路径不能为空".into());
    }
    app.opener()
        .open_path(trimmed, None::<&str>)
        .map_err(|e| e.to_string())
}

/// 用系统默认程序打开本地文件或文件夹
#[tauri::command]
pub fn open_local_path(app: AppHandle, path: String) -> Result<(), String> {
    let trimmed = path.trim();
    if trimmed.is_empty() {
        return Err("路径不能为空".into());
    }
    app.opener()
        .open_path(trimmed, None::<&str>)
        .map_err(|e| e.to_string())
}

/// 在文件管理器中定位并选中文件/文件夹
#[tauri::command]
pub fn reveal_in_explorer(app: AppHandle, path: String) -> Result<(), String> {
    let trimmed = path.trim();
    if trimmed.is_empty() {
        return Err("路径不能为空".into());
    }
    app.opener()
        .reveal_item_in_dir(trimmed)
        .map_err(|e| e.to_string())
}

/// 用默认浏览器打开 URL
#[tauri::command]
pub fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("URL 不能为空".into());
    }
    app.opener()
        .open_url(trimmed, None::<&str>)
        .map_err(|e| e.to_string())
}
