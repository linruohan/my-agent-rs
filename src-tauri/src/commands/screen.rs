use base64::{engine::general_purpose::STANDARD, Engine as _};
use screenshots::Screen;
use tauri::command;

#[command]
pub async fn capture_screen() -> Result<String, String> {
    tokio::task::spawn_blocking(|| {
        let screens = Screen::all().map_err(|e| e.to_string())?;
        let screen = screens
            .into_iter()
            .next()
            .ok_or_else(|| "No display found".to_string())?;
        let buffer = screen.capture().map_err(|e| e.to_string())?;
        let width = buffer.width();
        let height = buffer.height();
        let raw = buffer.into_raw();
        let rgba = image::RgbaImage::from_raw(width, height, raw)
            .ok_or_else(|| "Invalid screen buffer".to_string())?;
        let dynamic = image::DynamicImage::ImageRgba8(rgba);
        let mut png_bytes = Vec::new();
        dynamic
            .write_to(
                &mut std::io::Cursor::new(&mut png_bytes),
                image::ImageFormat::Png,
            )
            .map_err(|e| e.to_string())?;
        Ok(STANDARD.encode(png_bytes))
    })
    .await
    .map_err(|e| e.to_string())?
}
