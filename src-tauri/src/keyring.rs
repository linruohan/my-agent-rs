use keyring::Entry;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::command;
use tauri::AppHandle;
use tauri::Manager;

const SERVICE_NAME: &str = "personal-assistant-agent";

const PROVIDER_ENV_MAP: [(&str, &str); 11] = [
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("qwen", "DASHSCOPE_API_KEY"),
    ("moonshot", "MOONSHOT_API_KEY"),
    ("zhipu", "ZHIPU_API_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("siliconflow", "SILICONFLOW_API_KEY"),
    ("custom", "CUSTOM_API_KEY"),
    ("ollama", "OLLAMA_API_KEY"),
    ("github", "GITHUB_TOKEN"),
];

fn secrets_path(data_dir: &Path, provider: &str) -> PathBuf {
    data_dir.join("secrets").join(format!("{provider}.key"))
}

fn read_keyring_key(provider: &str) -> Option<String> {
    let entry = Entry::new(SERVICE_NAME, provider).ok()?;
    let key = entry.get_password().ok()?;
    if key.trim().is_empty() {
        None
    } else {
        Some(key)
    }
}

fn read_file_key(data_dir: &Path, provider: &str) -> Option<String> {
    let key = std::fs::read_to_string(secrets_path(data_dir, provider))
        .ok()?
        .trim()
        .to_string();
    if key.is_empty() {
        None
    } else {
        Some(key)
    }
}

fn read_provider_key(provider: &str, data_dir: Option<&Path>) -> Option<String> {
    read_keyring_key(provider).or_else(|| {
        data_dir.and_then(|dir| read_file_key(dir, provider))
    })
}

fn write_file_key(data_dir: &Path, provider: &str, api_key: &str) -> Result<(), String> {
    let dir = data_dir.join("secrets");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(secrets_path(data_dir, provider), api_key).map_err(|e| e.to_string())
}

fn provider_has_key(provider: &str, data_dir: Option<&Path>) -> bool {
    read_provider_key(provider, data_dir).is_some()
}

#[command]
pub fn store_api_key(app: AppHandle, provider: String, api_key: String) -> Result<(), String> {
    let api_key = api_key.trim().to_string();
    if api_key.is_empty() {
        return Err("API Key 不能为空".to_string());
    }

    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

    let mut errors: Vec<String> = Vec::new();

    match Entry::new(SERVICE_NAME, &provider) {
        Ok(entry) => match entry.set_password(&api_key) {
            Ok(()) => log::info!("Stored API key for {provider} in Windows keyring"),
            Err(e) => errors.push(format!("密钥链写入失败: {e}")),
        },
        Err(e) => errors.push(format!("密钥链不可用: {e}")),
    }

    match write_file_key(&data_dir, &provider, &api_key) {
        Ok(()) => log::info!("Stored API key for {provider} in app data secrets"),
        Err(e) => errors.push(format!("本地密钥文件写入失败: {e}")),
    }

    if provider_has_key(&provider, Some(&data_dir)) {
        Ok(())
    } else {
        Err(errors.join("；"))
    }
}

#[command]
pub fn get_api_key(app: AppHandle, provider: String) -> Result<String, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    read_provider_key(&provider, Some(&data_dir))
        .ok_or_else(|| "未找到 API Key".to_string())
}

#[command]
pub fn delete_api_key(app: AppHandle, provider: String) -> Result<(), String> {
    if let Ok(entry) = Entry::new(SERVICE_NAME, &provider) {
        let _ = entry.delete_credential();
    }
    if let Ok(data_dir) = app.path().app_data_dir() {
        let path = secrets_path(&data_dir, &provider);
        let _ = std::fs::remove_file(path);
    }
    Ok(())
}

fn provider_api_key_env(provider_id: &str) -> String {
    let safe: String = provider_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c.to_ascii_uppercase()
            } else {
                '_'
            }
        })
        .collect();
    format!("PA_{}_API_KEY", safe)
}

fn inject_dynamic_provider_keys(cmd: &mut Command, data_dir: &Path) {
    let secrets_dir = data_dir.join("secrets");
    if !secrets_dir.is_dir() {
        return;
    }
    if let Ok(entries) = std::fs::read_dir(&secrets_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("key") {
                continue;
            }
            let stem = path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or_default();
            if stem.is_empty() {
                continue;
            }
            if let Some(key) = read_provider_key(stem, Some(data_dir)) {
                let env_var = provider_api_key_env(stem);
                log::info!("Injecting env {env_var} for provider {stem}");
                cmd.env(env_var, key);
            }
        }
    }
}

/// Inject stored API keys into dev-mode std::process::Command.
pub fn inject_api_keys(cmd: &mut Command, data_dir: &Path) {
    for (provider, env_var) in PROVIDER_ENV_MAP {
        if let Some(key) = read_provider_key(provider, Some(data_dir)) {
            log::info!("Injecting env {env_var} for provider {provider}");
            cmd.env(env_var, key);
        }
    }
    inject_dynamic_provider_keys(cmd, data_dir);
}

/// Inject data dir and API keys into Tauri sidecar shell command.
pub fn apply_sidecar_env(
    sidecar: tauri_plugin_shell::process::Command,
    data_dir: &Path,
) -> tauri_plugin_shell::process::Command {
    let mut cmd = sidecar.env("AGENT_DATA_DIR", data_dir);
    for (provider, env_var) in PROVIDER_ENV_MAP {
        if let Some(key) = read_provider_key(provider, Some(data_dir)) {
            log::info!("Injecting env {env_var} for provider {provider}");
            cmd = cmd.env(env_var, key);
        }
    }
    let secrets_dir = data_dir.join("secrets");
    if secrets_dir.is_dir() {
        if let Ok(entries) = std::fs::read_dir(&secrets_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) != Some("key") {
                    continue;
                }
                let stem = path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or_default();
                if stem.is_empty() {
                    continue;
                }
                if let Some(key) = read_provider_key(stem, Some(data_dir)) {
                    let env_var = provider_api_key_env(stem);
                    log::info!("Injecting env {env_var} for provider {stem}");
                    cmd = cmd.env(env_var, key);
                }
            }
        }
    }
    cmd
}

#[command]
pub fn list_stored_providers(app: AppHandle) -> Result<Vec<String>, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let mut found = std::collections::HashSet::new();
    for (provider, _) in PROVIDER_ENV_MAP {
        if provider_has_key(provider, Some(&data_dir)) {
            found.insert(provider.to_string());
        }
    }
    let secrets_dir = data_dir.join("secrets");
    if secrets_dir.is_dir() {
        if let Ok(entries) = std::fs::read_dir(&secrets_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("key") {
                    if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                        if provider_has_key(stem, Some(&data_dir)) {
                            found.insert(stem.to_string());
                        }
                    }
                }
            }
        }
    }
    let mut list: Vec<String> = found.into_iter().collect();
    list.sort();
    Ok(list)
}
