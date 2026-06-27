use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

use reqwest::Client;
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::ShellExt;
use tokio::sync::Mutex;

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
    sidecar_child: Option<tauri_plugin_shell::process::CommandChild>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            status: SidecarStatus::Stopped,
            port: None,
            child: None,
            sidecar_child: None,
        }
    }

    pub async fn start(&mut self, app: &AppHandle) -> Result<u16, String> {
        if self.status != SidecarStatus::Stopped {
            let _ = self.stop();
        }
        let result = if cfg!(debug_assertions) {
            self.start_dev_mode(app).await
        } else {
            self.start_production_sidecar(app).await
        };
        if result.is_err() {
            self.status = SidecarStatus::Error;
            let _ = app.emit("sidecar-status", &self.status);
        }
        result
    }

    pub async fn start_dev_mode(&mut self, app: &AppHandle) -> Result<u16, String> {
        self.status = SidecarStatus::Starting;
        let _ = app.emit("sidecar-status", &self.status);

        let agent_dir = std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join("agent");
        let config_dir = agent_dir.join("config");
        let data_dir = agent_dir
            .parent()
            .map(|p| p.join("data"))
            .unwrap_or_else(|| agent_dir.join("data"));

        let python = if cfg!(windows) { "python" } else { "python3" };

        let mut child = Command::new(python);
        child.args(["main.py", "--host", "127.0.0.1", "--port", "0"]);
        child.current_dir(&agent_dir);
        child.env("AGENT_CONFIG_DIR", &config_dir);
        child.env("AGENT_DATA_DIR", &data_dir);
        child.stdout(Stdio::piped());
        child.stderr(Stdio::piped());

        crate::keyring::inject_api_keys(&mut child);

        let mut child = child
            .spawn()
            .map_err(|e| format!("Failed to start sidecar: {e}"))?;

        let port = Self::wait_for_ready_stdout(&mut child)?;
        self.child = Some(child);
        self.port = Some(port);
        self.status = SidecarStatus::Running;
        let _ = app.emit("sidecar-status", &self.status);
        let _ = app.emit("sidecar-port", port);
        Self::wait_for_health(port).await?;
        Ok(port)
    }

    pub async fn start_production_sidecar(&mut self, app: &AppHandle) -> Result<u16, String> {
        self.status = SidecarStatus::Starting;
        let _ = app.emit("sidecar-status", &self.status);

        let data_dir = app
            .path()
            .app_data_dir()
            .map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

        // Config is embedded in the PyInstaller binary (_MEIPASS/config).
        // Do not override AGENT_CONFIG_DIR with a non-existent resource path.
        let sidecar = app
            .shell()
            .sidecar("agent-api")
            .map_err(|e| format!("Sidecar not found: {e}"))?
            .args(["--host", "127.0.0.1", "--port", "0"]);

        let sidecar = crate::keyring::apply_sidecar_env(sidecar, &data_dir);

        let (mut rx, child) = sidecar.spawn().map_err(|e| format!("Spawn failed: {e}"))?;

        let port = tokio::task::spawn_blocking(move || {
            let deadline = std::time::Instant::now() + Duration::from_secs(120);
            while std::time::Instant::now() < deadline {
                if let Some(event) = rx.blocking_recv() {
                    match event {
                        tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                            let text = String::from_utf8_lossy(&line);
                            log::info!("sidecar: {text}");
                            if let Some(rest) = text.trim().strip_prefix("READY port=") {
                                if let Ok(port) = rest.parse::<u16>() {
                                    return Ok(port);
                                }
                            }
                        }
                        tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                            let text = String::from_utf8_lossy(&line);
                            log::error!("sidecar stderr: {text}");
                        }
                        _ => {}
                    }
                } else {
                    break;
                }
            }
            Err("Sidecar startup timeout".to_string())
        })
        .await
        .map_err(|e| e.to_string())??;

        self.sidecar_child = Some(child);
        self.port = Some(port);
        if let Err(e) = Self::wait_for_health(port).await {
            if let Some(child) = self.sidecar_child.take() {
                let _ = child.kill();
            }
            self.port = None;
            self.status = SidecarStatus::Error;
            let _ = app.emit("sidecar-status", &self.status);
            return Err(e);
        }
        self.status = SidecarStatus::Running;
        let _ = app.emit("sidecar-status", &self.status);
        let _ = app.emit("sidecar-port", port);
        Ok(port)
    }

    fn wait_for_ready_stdout(child: &mut Child) -> Result<u16, String> {
        let stdout = child.stdout.take().ok_or("No stdout from sidecar")?;
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

    async fn wait_for_health(port: u16) -> Result<(), String> {
        const EXPECTED_VERSION: &str = env!("CARGO_PKG_VERSION");

        #[derive(serde::Deserialize)]
        struct HealthResponse {
            status: String,
            version: String,
        }

        let client = Client::new();
        let url = format!("http://127.0.0.1:{port}/health");
        for _ in 0..10 {
            if let Ok(resp) = client.get(&url).send().await {
                if resp.status().is_success() {
                    let body: HealthResponse = resp
                        .json()
                        .await
                        .map_err(|e| format!("Invalid health response: {e}"))?;
                    if body.status != "ok" {
                        return Err(format!("Sidecar unhealthy: status={}", body.status));
                    }
                    if body.version != EXPECTED_VERSION {
                        return Err(format!(
                            "Sidecar version mismatch: expected {EXPECTED_VERSION}, got {}",
                            body.version
                        ));
                    }
                    log::info!("Sidecar health OK (v{})", body.version);
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

        if let Some(child) = self.sidecar_child.take() {
            let _ = child.kill();
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
    let mut manager = state.lock().await;
    manager.start(&app).await
}

#[tauri::command]
pub async fn stop_sidecar(state: State<'_, Mutex<SidecarManager>>) -> Result<(), String> {
    let mut manager = state.lock().await;
    manager.stop()
}

#[tauri::command]
pub async fn get_sidecar_status(
    state: State<'_, Mutex<SidecarManager>>,
) -> Result<(SidecarStatus, Option<u16>), String> {
    let manager = state.lock().await;
    Ok((manager.status.clone(), manager.port))
}
