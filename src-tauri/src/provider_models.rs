use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct FetchModelsResponse {
    pub models: Vec<String>,
}

fn normalize_openai_base_url(base_url: &str) -> String {
    let mut url = base_url.trim().trim_end_matches('/').to_string();
    for suffix in ["/chat/completions", "/completions"] {
        if url.ends_with(suffix) {
            url = url[..url.len() - suffix.len()].trim_end_matches('/').to_string();
        }
    }
    url
}

fn push_model_id(models: &mut Vec<String>, seen: &mut std::collections::BTreeSet<String>, raw: &str) {
    let id = raw.trim();
    if id.is_empty() || seen.contains(id) {
        return;
    }
    seen.insert(id.to_string());
    models.push(id.to_string());
}

fn parse_model_ids(data: &serde_json::Value) -> Vec<String> {
    let mut models: Vec<String> = Vec::new();
    let mut seen = std::collections::BTreeSet::new();

    if let Some(items) = data.get("data").and_then(|v| v.as_array()) {
        for item in items {
            if let Some(obj) = item.as_object() {
                let id = obj
                    .get("id")
                    .or_else(|| obj.get("name"))
                    .or_else(|| obj.get("model"))
                    .and_then(|v| v.as_str());
                if let Some(id) = id {
                    push_model_id(&mut models, &mut seen, id);
                }
            }
        }
    }

    if let Some(items) = data.get("models").and_then(|v| v.as_array()) {
        for item in items {
            if let Some(obj) = item.as_object() {
                let id = obj
                    .get("id")
                    .or_else(|| obj.get("name"))
                    .or_else(|| obj.get("model"))
                    .and_then(|v| v.as_str());
                if let Some(id) = id {
                    push_model_id(&mut models, &mut seen, id);
                }
            } else if let Some(s) = item.as_str() {
                push_model_id(&mut models, &mut seen, s);
            }
        }
    }

    if let Some(arr) = data.as_array() {
        for item in arr {
            if let Some(obj) = item.as_object() {
                let id = obj
                    .get("id")
                    .or_else(|| obj.get("name"))
                    .or_else(|| obj.get("model"))
                    .and_then(|v| v.as_str());
                if let Some(id) = id {
                    push_model_id(&mut models, &mut seen, id);
                }
            } else if let Some(s) = item.as_str() {
                push_model_id(&mut models, &mut seen, s);
            }
        }
    }

    models.sort();
    models
}

#[tauri::command]
pub async fn fetch_openai_compatible_models(
    base_url: String,
    api_key: String,
) -> Result<FetchModelsResponse, String> {
    let api_key = api_key.trim();
    if api_key.is_empty() {
        return Err("API Key 不能为空".to_string());
    }

    let base = normalize_openai_base_url(&base_url);
    if base.is_empty() {
        return Err("Base URL 不能为空".to_string());
    }

    let url = format!("{}/models", base);
    let client = reqwest::Client::new();
    let resp = client
        .get(&url)
        .header("Authorization", format!("Bearer {api_key}"))
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|e| format!("无法连接 API: {e}"))?;

    let status = resp.status();
    if !status.is_success() {
        let text = resp.text().await.unwrap_or_default();
        let snippet: String = text.chars().take(300).collect();
        return Err(format!("上游 API 错误 {}: {}", status.as_u16(), snippet));
    }

    let data: serde_json::Value = resp
        .json()
        .await
        .map_err(|e| format!("解析模型列表失败: {e}"))?;
    let models = parse_model_ids(&data);
    if models.is_empty() {
        return Err("未获取到模型，请检查 Base URL 与 API Key".to_string());
    }

    Ok(FetchModelsResponse { models })
}
