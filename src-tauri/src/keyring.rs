use keyring::Entry;
use std::process::Command;
use tauri::command;

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

#[command]
pub fn store_api_key(provider: String, api_key: String) -> Result<(), String> {
    let entry = Entry::new(SERVICE_NAME, &provider).map_err(|e| e.to_string())?;
    entry.set_password(&api_key).map_err(|e| e.to_string())
}

#[command]
pub fn get_api_key(provider: String) -> Result<String, String> {
    let entry = Entry::new(SERVICE_NAME, &provider).map_err(|e| e.to_string())?;
    entry.get_password().map_err(|e| e.to_string())
}

#[command]
pub fn delete_api_key(provider: String) -> Result<(), String> {
    let entry = Entry::new(SERVICE_NAME, &provider).map_err(|e| e.to_string())?;
    entry.delete_credential().map_err(|e| e.to_string())
}

/// Inject stored API keys into dev-mode std::process::Command.
pub fn inject_api_keys(cmd: &mut Command) {
    for (provider, env_var) in PROVIDER_ENV_MAP {
        if let Ok(entry) = Entry::new(SERVICE_NAME, provider) {
            if let Ok(key) = entry.get_password() {
                if !key.is_empty() {
                    cmd.env(env_var, key);
                }
            }
        }
    }
}

/// Inject data dir and API keys into Tauri sidecar shell command.
pub fn apply_sidecar_env(
    sidecar: tauri_plugin_shell::process::Command,
    data_dir: &std::path::Path,
) -> tauri_plugin_shell::process::Command {
    let mut cmd = sidecar.env("AGENT_DATA_DIR", data_dir);
    for (provider, env_var) in PROVIDER_ENV_MAP {
        if let Ok(entry) = Entry::new(SERVICE_NAME, provider) {
            if let Ok(key) = entry.get_password() {
                if !key.is_empty() {
                    cmd = cmd.env(env_var, key);
                }
            }
        }
    }
    cmd
}

#[command]
pub fn list_stored_providers() -> Result<Vec<String>, String> {
    let mut found = Vec::new();
    for (provider, _) in PROVIDER_ENV_MAP {
        if let Ok(entry) = Entry::new(SERVICE_NAME, provider) {
            if entry.get_password().is_ok() {
                found.push(provider.to_string());
            }
        }
    }
    Ok(found)
}
