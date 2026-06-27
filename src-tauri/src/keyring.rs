use keyring::Entry;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::command;
use tauri::AppHandle;
use tauri::Manager;

const SERVICE_NAME: &str = "personal-assistant-agent";

const PROVIDER_ENV_MAP: [(&str, &str); 7] = [
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("qwen", "DASHSCOPE_API_KEY"),
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

/// Inject stored API keys into dev-mode std::process::Command.
pub fn inject_api_keys(cmd: &mut Command, data_dir: &Path) {
    for (provider, env_var) in PROVIDER_ENV_MAP {
        if let Some(key) = read_provider_key(provider, Some(data_dir)) {
            log::info!("Injecting env {env_var} for provider {provider}");
            cmd.env(env_var, key);
        }
    }
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
    cmd
}

#[command]
pub fn list_stored_providers(app: AppHandle) -> Result<Vec<String>, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let mut found = Vec::new();
    for (provider, _) in PROVIDER_ENV_MAP {
        if provider_has_key(provider, Some(&data_dir)) {
            found.push(provider.to_string());
        }
    }
    Ok(found)
}
