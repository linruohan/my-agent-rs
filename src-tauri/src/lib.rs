mod commands;
mod keyring;
mod llm_config;
mod native_bridge;
mod sidecar;
mod tray;

use sidecar::SidecarManager;
use tokio::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Mutex::new(SidecarManager::new()))
        .invoke_handler(tauri::generate_handler![
            sidecar::start_sidecar,
            sidecar::stop_sidecar,
            sidecar::get_sidecar_status,
            keyring::store_api_key,
            keyring::get_api_key,
            keyring::delete_api_key,
            keyring::list_stored_providers,
            llm_config::get_llm_user_config,
            llm_config::store_llm_user_config,
            commands::screen::capture_screen,
            native_bridge::get_sidecar_token,
        ])
        .setup(|app| {
            tray::setup_tray(app.handle())?;

            if let Some(window) = app.get_webview_window("main") {
                let w = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = w.hide();
                    }
                });
            }

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let data_dir = match handle.path().app_data_dir() {
                    Ok(d) => d,
                    Err(e) => {
                        log::error!("App data dir: {e}");
                        return;
                    }
                };
                let _ = std::fs::create_dir_all(&data_dir);
                let token = native_bridge::ensure_sidecar_token(&data_dir);

                match native_bridge::NativeBridge::start(std::sync::Arc::new(token.clone())).await
                {
                    Ok(bridge) => {
                        let bridge_port = bridge.port();
                        let state = handle.state::<Mutex<SidecarManager>>();
                        let mut manager = state.lock().await;
                        manager.set_native_env(token, bridge_port, bridge);
                    }
                    Err(e) => log::error!("Native bridge failed: {e}"),
                }

                let state = handle.state::<Mutex<SidecarManager>>();
                let mut manager = state.lock().await;
                match manager.start(&handle).await {
                    Ok(port) => log::info!("Sidecar started on port {port}"),
                    Err(e) => log::error!("Failed to start sidecar: {e}"),
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
