use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct CustomProviderConfig {
    pub base_url: String,
    pub model: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CustomProviderEntry {
    pub id: String,
    pub name: String,
    pub base_url: String,
    pub model: String,
}

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct LlmUserConfig {
    pub default_provider: String,
    #[serde(default)]
    pub custom: Option<CustomProviderConfig>,
    #[serde(default)]
    pub custom_providers: Option<Vec<CustomProviderEntry>>,
    #[serde(default)]
    pub provider_models: Option<std::collections::HashMap<String, String>>,
}

fn config_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|d| d.join("llm_user.yaml"))
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_llm_user_config(app: AppHandle) -> Result<LlmUserConfig, String> {
    let path = config_path(&app)?;
    if !path.exists() {
        return Ok(LlmUserConfig {
            default_provider: "deepseek".to_string(),
            custom: None,
            custom_providers: None,
            provider_models: None,
        });
    }
    let text = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_yaml::from_str(&text).map_err(|e| format!("Invalid llm_user.yaml: {e}"))
}

#[tauri::command]
pub fn store_llm_user_config(app: AppHandle, config: LlmUserConfig) -> Result<(), String> {
    if let Some(providers) = &config.custom_providers {
        for entry in providers {
            if entry.id.trim().is_empty()
                || entry.name.trim().is_empty()
                || entry.base_url.trim().is_empty()
                || entry.model.trim().is_empty()
            {
                return Err("custom provider id, name, base_url and model cannot be empty".to_string());
            }
        }
    } else if config.default_provider == "custom" {
        let custom = config
            .custom
            .as_ref()
            .ok_or("custom provider requires base_url and model")?;
        if custom.base_url.trim().is_empty() || custom.model.trim().is_empty() {
            return Err("custom base_url and model cannot be empty".to_string());
        }
    }

    let path = config_path(&app)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let mut data = serde_yaml::Mapping::new();
    data.insert(
        serde_yaml::Value::from("default_provider"),
        serde_yaml::Value::from(config.default_provider.clone()),
    );

    if let Some(providers) = &config.custom_providers {
        let mut list = Vec::new();
        for entry in providers {
            let mut item = serde_yaml::Mapping::new();
            item.insert(
                serde_yaml::Value::from("id"),
                serde_yaml::Value::from(entry.id.clone()),
            );
            item.insert(
                serde_yaml::Value::from("name"),
                serde_yaml::Value::from(entry.name.clone()),
            );
            item.insert(
                serde_yaml::Value::from("base_url"),
                serde_yaml::Value::from(entry.base_url.clone()),
            );
            item.insert(
                serde_yaml::Value::from("model"),
                serde_yaml::Value::from(entry.model.clone()),
            );
            list.push(serde_yaml::Value::Mapping(item));
        }
        data.insert(
            serde_yaml::Value::from("custom_providers"),
            serde_yaml::Value::Sequence(list),
        );
    } else if config.default_provider == "custom" {
        if let Some(custom) = config.custom {
            let mut custom_map = serde_yaml::Mapping::new();
            custom_map.insert(
                serde_yaml::Value::from("base_url"),
                serde_yaml::Value::from(custom.base_url),
            );
            custom_map.insert(
                serde_yaml::Value::from("model"),
                serde_yaml::Value::from(custom.model),
            );
            data.insert(
                serde_yaml::Value::from("custom"),
                serde_yaml::Value::Mapping(custom_map),
            );
        }
    }

    if let Some(models) = config.provider_models {
        let mut models_map = serde_yaml::Mapping::new();
        for (name, model) in models {
            if !model.trim().is_empty() {
                models_map.insert(
                    serde_yaml::Value::from(name),
                    serde_yaml::Value::from(model),
                );
            }
        }
        if !models_map.is_empty() {
            data.insert(
                serde_yaml::Value::from("provider_models"),
                serde_yaml::Value::Mapping(models_map),
            );
        }
    }

    let yaml = serde_yaml::to_string(&data).map_err(|e| e.to_string())?;
    std::fs::write(path, yaml).map_err(|e| e.to_string())
}
