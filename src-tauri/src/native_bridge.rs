use std::path::Path;
use std::sync::Arc;

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tokio::sync::watch;

pub struct NativeBridge {
    port: u16,
    _shutdown: watch::Sender<()>,
}

impl NativeBridge {
    pub async fn start(token: Arc<String>) -> Result<Self, String> {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .map_err(|e| format!("Native bridge bind failed: {e}"))?;
        let port = listener
            .local_addr()
            .map_err(|e| e.to_string())?
            .port();
        let (shutdown_tx, shutdown_rx) = watch::channel(());

        tokio::spawn(run_server(listener, token, shutdown_rx));

        log::info!("Native bridge listening on 127.0.0.1:{port}");
        Ok(Self {
            port,
            _shutdown: shutdown_tx,
        })
    }

    pub fn port(&self) -> u16 {
        self.port
    }
}

async fn run_server(
    listener: TcpListener,
    token: Arc<String>,
    mut shutdown: watch::Receiver<()>,
) {
    loop {
        tokio::select! {
            changed = shutdown.changed() => {
                if changed.is_ok() {
                    break;
                }
            }
            accept = listener.accept() => {
                if let Ok((socket, _)) = accept {
                    let token = Arc::clone(&token);
                    tokio::spawn(handle_connection(socket, token));
                }
            }
        }
    }
}

async fn handle_connection(mut socket: tokio::net::TcpStream, token: Arc<String>) {
    let mut buf = vec![0u8; 8192];
    let n = match socket.read(&mut buf).await {
        Ok(n) if n > 0 => n,
        _ => return,
    };

    let request = String::from_utf8_lossy(&buf[..n]);
    let first_line = request.lines().next().unwrap_or("");

    let auth_ok = request.lines().any(|line| {
        let line = line.trim();
        line.starts_with("Authorization: Bearer ")
            && line.strip_prefix("Authorization: Bearer ")
                .map(|t| t == token.as_str())
                .unwrap_or(false)
    });

    if !auth_ok {
        let _ = socket
            .write_all(b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n")
            .await;
        return;
    }

    if first_line.starts_with("GET /screen") || first_line.starts_with("GET /native/screen") {
        match crate::commands::screen::capture_screen_b64().await {
            Ok(b64) => {
                let body = serde_json::json!({"base64": b64, "format": "png"}).to_string();
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(),
                    body
                );
                let _ = socket.write_all(response.as_bytes()).await;
            }
            Err(e) => {
                let body = serde_json::json!({"error": e}).to_string();
                let response = format!(
                    "HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(),
                    body
                );
                let _ = socket.write_all(response.as_bytes()).await;
            }
        }
        return;
    }

    if first_line.starts_with("GET /health") || first_line.starts_with("GET /native/health") {
        let body = r#"{"status":"ok"}"#;
        let response = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
            body.len(),
            body
        );
        let _ = socket.write_all(response.as_bytes()).await;
        return;
    }

    let _ = socket
        .write_all(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        .await;
}

pub fn ensure_sidecar_token(data_dir: &Path) -> String {
    let path = data_dir.join(".sidecar_token");
    if let Ok(existing) = std::fs::read_to_string(&path) {
        let token = existing.trim().to_string();
        if !token.is_empty() {
            return token;
        }
    }

    let token = format!(
        "{:x}{:x}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0),
        std::process::id() as u128
    );
    let _ = std::fs::create_dir_all(data_dir);
    let _ = std::fs::write(&path, &token);
    token
}

#[tauri::command]
pub fn get_sidecar_token(app: tauri::AppHandle) -> Result<String, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    Ok(ensure_sidecar_token(&data_dir))
}
