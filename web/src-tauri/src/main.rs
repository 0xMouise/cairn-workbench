#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{process::Command, time::Duration};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, WindowEvent,
};

fn wsl(args: &[&str]) -> Result<String, String> {
    let mut command = Command::new("wsl.exe");
    command.args(args);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let output = command.output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn connect_backend() -> Result<String, String> {
    // systemd services alone do not keep a WSL distribution alive.
    let mut guard = Command::new("wsl.exe");
    guard.args([
        "-d",
        "kali-linux",
        "--",
        "flock",
        "-n",
        "/tmp/cairn-workbench-host.lock",
        "bash",
        "-c",
        "exec -a cairn-workbench-host /bin/sleep infinity",
    ]);
    #[cfg(windows)]
    guard.creation_flags(0x08000000);
    guard.spawn().map_err(|e| e.to_string())?;
    wsl(&[
        "-d",
        "kali-linux",
        "--",
        "systemctl",
        "--user",
        "start",
        "cairn-workbench.service",
    ])?;
    let home = wsl(&["-d", "kali-linux", "--", "printenv", "HOME"])?;
    let token_path = format!("{}/.local/share/cairn-workbench/access-token", home);
    for _ in 0..40 {
        let token = wsl(&["-d", "kali-linux", "--", "cat", &token_path]);
        let listening = std::net::TcpStream::connect_timeout(
            &"127.0.0.1:18100".parse().unwrap(),
            Duration::from_millis(200),
        )
        .is_ok();
        if let Ok(token) = token {
            if !token.is_empty() && listening {
                return Ok(format!("http://127.0.0.1:18100/#token={}", token));
            }
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    Err("工作台服务未准备好。请查看 WSL 服务诊断日志。".to_string())
}

#[tauri::command]
async fn install_backend(app: tauri::AppHandle) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move||{
        let archive=app.path().resource_dir().map_err(|e|e.to_string())?.join("resources/runtime.tar.gz");
        let archive=archive.to_str().ok_or("安装包路径无效")?;
        let source=wsl(&["-d","kali-linux","--","wslpath","-a",archive])?;
        let script="import pathlib,tarfile,sys; p=pathlib.Path.home()/'apps/cairn-workbench'; p.mkdir(parents=True,exist_ok=True); tarfile.open(sys.argv[1]).extractall(p,filter='data'); print(p)";
        let root=wsl(&["-d","kali-linux","--","python3","-c",script,&source])?;
        wsl(&["-d","kali-linux","--","python3",&format!("{}/scripts/install_wsl.py",root)])?;
        connect_backend()
    }).await.map_err(|e|e.to_string())?
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![install_backend])
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {if let Some(w)=app.get_webview_window("main"){let _=w.show();let _=w.set_focus();}}))
        .setup(|app| {
            let show = MenuItem::with_id(app,"show","打开 Cairn Workbench",true,None::<&str>)?;
            let quit = MenuItem::with_id(app,"quit","退出桌面端（任务继续运行）",true,None::<&str>)?;
            let menu = Menu::with_items(app,&[&show,&quit])?;
            let mut tray=TrayIconBuilder::new().tooltip("Cairn Workbench").menu(&menu).on_menu_event(|app,event| match event.id.as_ref(){"show"=>{if let Some(w)=app.get_webview_window("main"){let _=w.show();let _=w.set_focus();}},"quit"=>app.exit(0),_=>{}});
            if let Some(icon)=app.default_window_icon(){tray=tray.icon(icon.clone());}
            let _=tray.build(app)?;
            let handle=app.handle().clone();
            std::thread::spawn(move||{
                let result=connect_backend();
                if let Some(w)=handle.get_webview_window("main"){
                    match result {Ok(address)=>{if let Ok(url)=address.parse(){let _=w.navigate(url);}},Err(message)=>{
                        let text=serde_json::to_string(&message).unwrap();
                        let _=w.eval(&format!("document.body.style='font:15px Segoe UI;padding:70px;background:#171819;color:#e8e9eb';document.body.innerHTML='<h1>Cairn Workbench</h1><p>准备你的本地研究环境</p><p id=message></p><p>需要已安装的 WSL Kali、Python 3.12+ 和 Node.js。确认后将下载依赖并安装独立后台服务。</p><button id=install style=padding:12px>安装工作台后端</button><pre id=result></pre>';document.getElementById('message').innerText={};document.getElementById('install').onclick=async function(){{this.disabled=true;document.getElementById('result').innerText='正在安装依赖，请稍候…';try{{location.href=await window.__TAURI__.core.invoke('install_backend')}}catch(e){{document.getElementById('result').innerText=String(e);this.disabled=false}}}};",text));
                    }}
                    let _=w.show();let _=w.set_focus();
                }
            });
            Ok(())
        })
        .on_window_event(|window,event|{if let WindowEvent::CloseRequested{api,..}=event{api.prevent_close();let _=window.hide();}})
        .run(tauri::generate_context!())
        .expect("Cairn Workbench desktop runtime failed");
}
