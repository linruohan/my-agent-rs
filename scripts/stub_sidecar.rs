//! Minimal Sidecar stub for Tauri dev/cargo check when PyInstaller binary is absent.
//! Prints READY and keeps running until killed.

use std::io::{self, Write};
use std::net::TcpListener;
use std::thread;
use std::time::Duration;

fn main() {
    let port = pick_port();
    println!("READY port={port}");
    let _ = io::stdout().flush();

    // Keep process alive; real sidecar is replaced in release builds.
    loop {
        thread::sleep(Duration::from_secs(3600));
    }
}

fn pick_port() -> u16 {
    for port in 8765..8800 {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return port;
        }
    }
    8765
}
