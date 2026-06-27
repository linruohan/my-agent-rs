mod commands;
mod keyring;
mod sidecar;

use sidecar::SidecarManager;
use std::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .manage(Mutex::new(SidecarManager::new()))
        .invoke_handler(tauri::generate_handler![
            sidecar::start_sidecar,
            sidecar::stop_sidecar,
            sidecar::get_sidecar_status,
            keyring::store_api_key,
            keyring::get_api_key,
            keyring::delete_api_key,
            commands::screen::capture_screen,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Ok(mut manager) = handle.state::<Mutex<SidecarManager>>().lock() {
                    match manager.start_dev_mode(&handle).await {
                        Ok(port) => log::info!("Sidecar started on port {port}"),
                        Err(e) => log::error!("Failed to start sidecar: {e}"),
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
