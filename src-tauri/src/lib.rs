mod commands;
mod keyring;
mod llm_config;
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
        ])
        .setup(|app| {
            tray::setup_tray(app.handle())?;

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
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
