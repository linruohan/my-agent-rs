use tauri::command;

#[command]
pub async fn capture_screen() -> Result<String, String> {
    Err("Screen capture not implemented yet (Phase 3)".to_string())
}
