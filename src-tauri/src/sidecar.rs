use std::process::{Child, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use reqwest::Client;
use serde::Serialize;
use tauri::{AppHandle, Emitter, State};

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum SidecarStatus {
    Stopped,
    Starting,
    Running,
    Error,
}

pub struct SidecarManager {
    pub status: SidecarStatus,
    pub port: Option<u16>,
    child: Option<Child>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            status: SidecarStatus::Stopped,
            port: None,
            child: None,
        }
    }

    pub async fn start_dev_mode(&mut self, app: &AppHandle) -> Result<u16, String> {
        self.status = SidecarStatus::Starting;
        let _ = app.emit("sidecar-status", &self.status);

        let agent_dir = std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join("agent");

        let python = if cfg!(windows) { "python" } else { "python3" };

        let mut child = std::process::Command::new(python)
            .args(["main.py", "--host", "127.0.0.1", "--port", "0"])
            .current_dir(&agent_dir)
            .env("AGENT_CONFIG_DIR", agent_dir.join("config"))
            .env("AGENT_DATA_DIR", agent_dir.parent().unwrap().join("data"))
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start sidecar: {e}"))?;

        let port = self.wait_for_ready(&mut child).await?;
        self.child = Some(child);
        self.port = Some(port);
        self.status = SidecarStatus::Running;
        let _ = app.emit("sidecar-status", &self.status);
        let _ = app.emit("sidecar-port", port);

        self.wait_for_health(port).await?;
        Ok(port)
    }

    async fn wait_for_ready(&self, child: &mut Child) -> Result<u16, String> {
        use std::io::{BufRead, BufReader};

        let stdout = child
            .stdout
            .take()
            .ok_or("No stdout from sidecar")?;
        let reader = BufReader::new(stdout);

        let deadline = std::time::Instant::now() + Duration::from_secs(30);
        for line in reader.lines() {
            if std::time::Instant::now() > deadline {
                return Err("Sidecar startup timeout".to_string());
            }
            let line = line.map_err(|e| e.to_string())?;
            log::info!("sidecar: {line}");
            if line.starts_with("READY port=") {
                let port_str = line.trim_start_matches("READY port=");
                return port_str
                    .parse::<u16>()
                    .map_err(|e| format!("Invalid port: {e}"));
            }
        }
        Err("Sidecar exited before READY".to_string())
    }

    async fn wait_for_health(&self, port: u16) -> Result<(), String> {
        let client = Client::new();
        let url = format!("http://127.0.0.1:{port}/health");
        for _ in 0..10 {
            if let Ok(resp) = client.get(&url).send().await {
                if resp.status().is_success() {
                    return Ok(());
                }
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
        Err("Sidecar health check failed".to_string())
    }

    pub fn stop(&mut self) -> Result<(), String> {
        if let Some(port) = self.port {
            let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
            let _ = rt.block_on(async {
                Client::new()
                    .post(format!("http://127.0.0.1:{port}/shutdown"))
                    .send()
                    .await
            });
        }

        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }

        self.status = SidecarStatus::Stopped;
        self.port = None;
        Ok(())
    }
}

#[tauri::command]
pub async fn start_sidecar(
    state: State<'_, Mutex<SidecarManager>>,
    app: AppHandle,
) -> Result<u16, String> {
    let mut manager = state.lock().map_err(|e| e.to_string())?;
    manager.start_dev_mode(&app).await
}

#[tauri::command]
pub async fn stop_sidecar(state: State<'_, Mutex<SidecarManager>>) -> Result<(), String> {
    let mut manager = state.lock().map_err(|e| e.to_string())?;
    manager.stop()
}

#[tauri::command]
pub async fn get_sidecar_status(
    state: State<'_, Mutex<SidecarManager>>,
) -> Result<(SidecarStatus, Option<u16>), String> {
    let manager = state.lock().map_err(|e| e.to_string())?;
    Ok((manager.status.clone(), manager.port))
}
