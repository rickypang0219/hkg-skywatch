#[cfg(target_arch = "wasm32")]
mod browser;
fn main() {
    #[cfg(target_arch = "wasm32")]
    browser::start();
    #[cfg(not(target_arch = "wasm32"))]
    println!("Run `trunk serve` to launch the WebAssembly app.");
}
