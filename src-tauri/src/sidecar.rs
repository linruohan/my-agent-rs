use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
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
    auth_token: Option<String>,
    native_bridge_port: Option<u16>,
    _native_bridge: Option<crate::native_bridge::NativeBridge>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            status: SidecarStatus::Stopped,
            port: None,
            child: None,
            sidecar_child: None,
            auth_token: None,
            native_bridge_port: None,
            _native_bridge: None,
        }
    }

    pub fn set_native_env(
        &mut self,
        token: String,
        bridge_port: u16,
        bridge: crate::native_bridge::NativeBridge,
    ) {
        self.auth_token = Some(token);
        self.native_bridge_port = Some(bridge_port);
        self._native_bridge = Some(bridge);
    }

    fn apply_native_env(&self, cmd: &mut Command) {
        cmd.env("AGENT_EXPECTED_VERSION", env!("CARGO_PKG_VERSION"));
        cmd.env("AGENT_API_VERSION", env!("CARGO_PKG_VERSION"));
        if let Some(ref token) = self.auth_token {
            cmd.env("SIDECAR_AUTH_TOKEN", token);
        }
        if let Some(port) = self.native_bridge_port {
            cmd.env(
                "NATIVE_BRIDGE_URL",
                format!("http://127.0.0.1:{port}"),
            );
        }
    }

    fn apply_native_env_sidecar(
        &self,
        sidecar: tauri_plugin_shell::process::Command,
    ) -> tauri_plugin_shell::process::Command {
        let mut cmd = sidecar.env("AGENT_EXPECTED_VERSION", env!("CARGO_PKG_VERSION"));
        cmd = cmd.env("AGENT_API_VERSION", env!("CARGO_PKG_VERSION"));
        if let Some(ref token) = self.auth_token {
            cmd = cmd.env("SIDECAR_AUTH_TOKEN", token);
        }
        if let Some(port) = self.native_bridge_port {
            cmd = cmd.env("NATIVE_BRIDGE_URL", format!("http://127.0.0.1:{port}"));
        }
        cmd
    }

    pub async fn start(&mut self, app: &AppHandle, boot_start: std::time::Instant) -> Result<u16, String> {
        if self.status != SidecarStatus::Stopped {
            self.stop_async().await?;
        }
        let result = if cfg!(debug_assertions) {
            self.start_dev_mode(app, boot_start).await
        } else {
            self.start_production_sidecar(app, boot_start).await
        };
        if result.is_err() {
            self.status = SidecarStatus::Error;
            let _ = app.emit("sidecar-status", &self.status);
        }
        result
    }

    pub async fn start_dev_mode(&mut self, app: &AppHandle, boot_start: std::time::Instant) -> Result<u16, String> {
        self.status = SidecarStatus::Starting;
        let _ = app.emit("sidecar-status", &self.status);

        let (agent_dir, config_dir, data_dir) = Self::dev_agent_paths(app)?;

        let python = if cfg!(windows) { "python" } else { "python3" };

        let mut child = Command::new(python);
        child.args(["main.py", "--host", "127.0.0.1", "--port", "0"]);
        child.current_dir(&agent_dir);
        child.env("AGENT_CONFIG_DIR", &config_dir);
        child.env("AGENT_DATA_DIR", &data_dir);
        self.apply_native_env(&mut child);
        child.stdout(Stdio::piped());
        child.stderr(Stdio::inherit());

        crate::keyring::inject_api_keys(&mut child, &data_dir);

        let mut child = child
            .spawn()
            .map_err(|e| format!("Failed to start sidecar: {e}"))?;
        log::info!(
            "[startup] +{}ms Sidecar process spawned (dev python)",
            boot_start.elapsed().as_millis()
        );

        let port = Self::wait_for_ready_stdout(&mut child, Duration::from_secs(60), boot_start)?;
        self.child = Some(child);
        self.port = Some(port);
        self.status = SidecarStatus::Running;
        let _ = app.emit("sidecar-status", &self.status);
        let _ = app.emit("sidecar-port", port);
        Self::wait_for_health(port, boot_start).await?;
        Ok(port)
    }

    pub async fn start_production_sidecar(&mut self, app: &AppHandle, boot_start: std::time::Instant) -> Result<u16, String> {
        self.status = SidecarStatus::Starting;
        let _ = app.emit("sidecar-status", &self.status);

        let data_dir = app
            .path()
            .app_data_dir()
            .map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

        match crate::sidecar_update::sync_from_bundle(app, &data_dir) {
            Ok(true) => {
                let _ = app.emit("sidecar-updated", env!("CARGO_PKG_VERSION"));
            }
            Ok(false) => {}
            Err(e) => log::warn!("Sidecar sync skipped: {e}"),
        }

        let installed = crate::sidecar_update::installed_binary(&data_dir);
        if installed.is_file() {
            return self
                .start_production_from_path(app, &data_dir, &installed, boot_start)
                .await;
        }

        // Fallback: Tauri shell sidecar (dev stub or missing sync)
        let sidecar = app
            .shell()
            .sidecar("agent-api")
            .map_err(|e| format!("Sidecar not found: {e}"))?
            .args(["--host", "127.0.0.1", "--port", "0"]);

        let sidecar = crate::keyring::apply_sidecar_env(sidecar, &data_dir);
        let sidecar = self.apply_native_env_sidecar(sidecar);

        let (mut rx, child) = sidecar.spawn().map_err(|e| format!("Spawn failed: {e}"))?;
        log::info!(
            "[startup] +{}ms Sidecar process spawned (shell sidecar)",
            boot_start.elapsed().as_millis()
        );

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
        if let Err(e) = Self::wait_for_health(port, boot_start).await {
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

    async fn start_production_from_path(
        &mut self,
        app: &AppHandle,
        data_dir: &Path,
        binary: &Path,
        boot_start: std::time::Instant,
    ) -> Result<u16, String> {
        let mut child = Command::new(binary);
        child.args(["--host", "127.0.0.1", "--port", "0"]);
        child.env("AGENT_DATA_DIR", data_dir);
        self.apply_native_env(&mut child);
        child.stdout(Stdio::piped());
        child.stderr(Stdio::inherit());
        crate::keyring::inject_api_keys(&mut child, data_dir);

        let mut child = child
            .spawn()
            .map_err(|e| format!("Failed to start synced sidecar: {e}"))?;
        log::info!(
            "[startup] +{}ms Sidecar process spawned (synced binary)",
            boot_start.elapsed().as_millis()
        );

        let port = Self::wait_for_ready_stdout(&mut child, Duration::from_secs(120), boot_start)?;
        self.child = Some(child);
        self.port = Some(port);
        if let Err(e) = Self::wait_for_health(port, boot_start).await {
            if let Some(mut child) = self.child.take() {
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

    fn dev_agent_paths(app: &AppHandle) -> Result<(PathBuf, PathBuf, PathBuf), String> {
        // `tauri dev` runs with cwd=src-tauri; agent lives at repo_root/agent
        let agent_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("agent");
        if !agent_dir.join("main.py").is_file() {
            return Err(format!(
                "Agent sidecar not found at {} (expected repo agent/main.py)",
                agent_dir.display()
            ));
        }
        let config_dir = agent_dir.join("config");
        let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
        Ok((agent_dir, config_dir, data_dir))
    }

    fn wait_for_ready_stdout(
        child: &mut Child,
        timeout: Duration,
        boot_start: std::time::Instant,
    ) -> Result<u16, String> {
        let stdout = child.stdout.take().ok_or("No stdout from sidecar")?;
        let reader = BufReader::new(stdout);
        let deadline = std::time::Instant::now() + timeout;
        for line in reader.lines() {
            if std::time::Instant::now() > deadline {
                return Err("Sidecar startup timeout".to_string());
            }
            let line = line.map_err(|e| e.to_string())?;
            log::info!("sidecar: {line}");
            if line.starts_with("READY port=") {
                log::info!(
                    "[startup] +{}ms Sidecar READY signal received",
                    boot_start.elapsed().as_millis()
                );
                let port_str = line.trim_start_matches("READY port=");
                return port_str
                    .parse::<u16>()
                    .map_err(|e| format!("Invalid port: {e}"));
            }
        }
        Err("Sidecar exited before READY".to_string())
    }

    async fn wait_for_health(port: u16, boot_start: std::time::Instant) -> Result<(), String> {
        const EXPECTED_VERSION: &str = env!("CARGO_PKG_VERSION");

        #[derive(serde::Deserialize)]
        struct HealthResponse {
            status: String,
            version: String,
            #[serde(default)]
            version_ok: bool,
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
                    if !body.version_ok {
                        log::warn!(
                            "Sidecar API version negotiation: version_ok=false (continuing)"
                        );
                    }
                    log::info!(
                        "[startup] +{}ms Sidecar health OK (v{})",
                        boot_start.elapsed().as_millis(),
                        body.version
                    );
                    return Ok(());
                }
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
        Err("Sidecar health check failed".to_string())
    }

    pub async fn stop_async(&mut self) -> Result<(), String> {
        if let Some(port) = self.port {
            let _ = Client::new()
                .post(format!("http://127.0.0.1:{port}/shutdown"))
                .send()
                .await;
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
    manager.start(&app, std::time::Instant::now()).await
}

#[tauri::command]
pub async fn stop_sidecar(state: State<'_, Mutex<SidecarManager>>) -> Result<(), String> {
    let mut manager = state.lock().await;
    manager.stop_async().await
}

#[tauri::command]
pub async fn restart_sidecar(
    state: State<'_, Mutex<SidecarManager>>,
    app: AppHandle,
) -> Result<u16, String> {
    let mut manager = state.lock().await;
    manager.stop_async().await?;
    manager.start(&app, std::time::Instant::now()).await
}

#[tauri::command]
pub async fn get_sidecar_status(
    state: State<'_, Mutex<SidecarManager>>,
) -> Result<(SidecarStatus, Option<u16>), String> {
    let manager = state.lock().await;
    Ok((manager.status.clone(), manager.port))
}
