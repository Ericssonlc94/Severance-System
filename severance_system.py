import json
import subprocess
import psutil
import threading
import time
import sys
import os
import winsound
import random
import string
import pygetwindow as gw
import shutil
import pyautogui
import glob
import ctypes
import winreg
import tkinter as tk
from tkinter import filedialog
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.status import Status
from rich.live import Live
from rich.align import Align
from rich.align import Align
from rich.layout import Layout
from rich.columns import Columns

# --- CONSTANTES ---
STYLE_BG = "on #0a2a4f"
STYLE_FG = "bright_cyan"
STYLE_ACCENT = "cyan"
STYLE_ERROR = "bold red"
STYLE_MATRIX = "bold green"
WORK_DB = "work_apps.json"
PERSONAL_DB = "personal_apps.json"

CONFIG_DB = "config.json" # New constant

console = Console(style=f"{STYLE_FG} {STYLE_BG}")

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_db_path(db_name):
    # Get the directory of the running executable
    exe_dir = os.path.dirname(sys.executable)
    # Ensure the directory exists (though it should if the exe is there)
    os.makedirs(exe_dir, exist_ok=True)
    return os.path.join(exe_dir, db_name)

def load_apps(db_name):
    db_path = get_db_path(db_name)
    try:
        with open(db_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_apps(db_name, apps):
    db_path = get_db_path(db_name)
    with open(db_path, "w") as f:
        json.dump(apps, f, indent=4)

def load_config(): # New function
    config_path = get_db_path(CONFIG_DB)
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} # Return empty dict if file not found or invalid JSON

def save_config(config): # New function
    config_path = get_db_path(CONFIG_DB)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

# --- FUNÇÕES DE GERENCIAMENTO DE PROCESSO ---
def manage_processes(apps_to_launch, apps_to_terminate, status):
    # 0. IDENTIFICAR APPS COMPARTILHADOS (NOVO)
    launch_paths = {os.path.normcase(app['path']) for app in apps_to_launch}
    apps_to_launch_names_lower = {app['name'].lower() for app in apps_to_launch} # New line
    apps_to_terminate = [
        app for app in apps_to_terminate
        if os.path.normcase(app['path']) not in launch_paths
    ]

    # 1. LÓGICA DE TÉRMINO DE APPS (MODIFICADA PARA MAIOR ROBUSTEZ)
    status.update("[bold yellow]TERMINANDO APLICATIVOS DO MODO ANTERIOR...[/bold yellow]")
    terminated_count = 0
    if apps_to_terminate:
        running_processes = {}
        for p in psutil.process_iter(['name']):
            try:
                name_lower = p.name().lower()
                if name_lower not in running_processes:
                    running_processes[name_lower] = []
                running_processes[name_lower].append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for app in apps_to_terminate:
            app_name_lower = app["name"].lower() # Use the app name from the config
            app_exe_name = os.path.basename(app["path"]).lower()

            if "dropbox" in app_name_lower or "dropbox" in app_exe_name:
                # Aggressively kill all processes related to Dropbox
                for p in psutil.process_iter(['name', 'exe']):
                    try:
                        p_name_lower = p.name().lower()
                        p_exe_lower = p.info['exe'].lower() if p.info['exe'] else ""
                        if "dropbox" in p_name_lower or "dropbox" in p_exe_lower:
                            # Check if this process was part of the original apps_to_terminate list
                            # This prevents killing unrelated Dropbox processes if Dropbox is not in apps_to_terminate
                            process_found_in_list = False
                            for original_app in apps_to_terminate:
                                if os.path.normcase(original_app['path']) == os.path.normcase(p.info['exe']):
                                    process_found_in_list = True
                                    break
                            
                            if process_found_in_list:
                                p.kill()
                                terminated_count += 1
                                console.log(f"[dim]TERMINADO (KILL AGRESSIVO):[/dim] {p.name()} (PID: {p.pid})")
                                time.sleep(0.1) # Small delay between kills
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            elif app_exe_name in running_processes:
                procs_to_terminate = running_processes[app_exe_name]
                for process in procs_to_terminate:
                    try:
                        process.terminate()
                        terminated_count += 1
                        console.log(f"[dim]TERMINADO:[/dim] {app['name']} (PID: {process.pid})")
                        time.sleep(0.2)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        console.log(f"[{STYLE_ERROR}]FALHA AO TERMINAR:[/{STYLE_ERROR}] {app['name']} (PID: {process.pid})")
                running_processes[app_exe_name] = []

    console.log(f"[bold green]{terminated_count} PROCESSOS TERMINADOS.[/bold green]")
    time.sleep(1)

    # 2. LÓGICA DE INÍCIO DE APPS (MODIFICADA PARA NÃO REINICIAR APPS)
    status.update("[bold yellow]INICIANDO APLICATIVOS DO MODO ATUAL...[/bold yellow]")
    launched_count = 0
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 6 # SW_MINIMIZE

    if apps_to_launch:
        running_app_paths = set()
        for p in psutil.process_iter(['exe']):
            try:
                if p.info['exe']:
                    running_app_paths.add(os.path.normcase(p.info['exe']))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        for app in apps_to_launch:
            if os.path.normcase(app["path"]) in running_app_paths:
                console.log(f"[dim]JÁ EM EXECUÇÃO:[/dim] {app['name']}")
                continue
            try:
                app_path = app["path"]
                app_name_lower = app["name"].lower()
                _, ext = os.path.splitext(app_path)

                command = [app_path]
                use_startupinfo = True

                if "steam" in app_name_lower:
                    command.append("-silent")
                    use_startupinfo = False
                
                elif "logitech" in app_name_lower:
                    command.append("--background")
                    use_startupinfo = False

                if ext.lower() == ".vbs":
                    script_dir = os.path.dirname(app_path)
                    subprocess.Popen(["wscript.exe", app_path], cwd=script_dir)
                
                elif "brave" in app_path.lower():
                    subprocess.Popen([app_path])
                
                else:
                    if use_startupinfo:
                        subprocess.Popen(command, startupinfo=startupinfo)
                    else:
                        subprocess.Popen(command)
                
                launched_count += 1
                console.log(f"[dim]INICIADO:[/dim] {app['name']}")
                time.sleep(0.2)
            except Exception as e:
                console.log(f"[{STYLE_ERROR}]FALHA AO INICIAR:[/{STYLE_ERROR}] {app['name']} - {e}")
    console.log(f"[bold green]{launched_count} APLICATIVOS INICIADOS.[/bold green]")
    time.sleep(1)

    # LÓGICA GENÉRICA PARA FECHAR JANELAS DE APPS MARCADOS
    apps_to_close = [app for app in apps_to_launch if app.get("close_after_launch")]
    if apps_to_close:
        status.update("[bold yellow]FINALIZANDO INTERFACES...[/bold yellow]")
        time.sleep(4)
        for app in apps_to_close:
            try:
                app_name = app.get("name")
                if not app_name: continue
                
                # Tenta encontrar a janela pelo nome do app (parcial e insensível a maiúsculas/minúsculas)
                windows = [w for w in gw.getAllWindows() if app_name.lower() in w.title.lower()]
                
                if not windows:
                    # Tenta uma busca mais curta se a primeira falhar
                    short_name = app_name.split()[0]
                    windows = [w for w in gw.getAllWindows() if short_name.lower() in w.title.lower()]

                if windows:
                    window = windows[0]
                    console.log(f"[dim]Fechando interface de '{window.title}' com Alt+F4...[/dim]")
                    window.activate()
                    time.sleep(1) # Increased delay
                    pyautogui.hotkey('alt', 'f4')
                    time.sleep(0.5)
            except Exception as e:
                console.log(f"[{STYLE_ERROR}]Não foi possível fechar a janela de '{app.get('name', 'unknown')}': {e}[/{STYLE_ERROR}]")

    # 3. LÓGICA PARA FECHAR PASTAS E JANELAS DE ERRO (EXISTENTE)
    status.update("[bold yellow]ORGANIZANDO ÁREA DE TRABALHO...[/bold yellow]")
    time.sleep(5) # Increased delay to allow error windows to appear
    closed_windows = 0 # Changed from closed_folders to closed_windows
    try:
        for window in gw.getAllWindows():
            # Fecha pastas do Drive e Dropbox, e janelas de erro do Dropbox
            title_lower = window.title.lower()
            if "google drive" in title_lower or \
               ("dropbox" in title_lower and ("erro" in title_lower or "terminado inesperadamente" in title_lower)):
                console.log(f"[dim]Fechando janela:[/dim] {window.title}")
                window.close()
                closed_windows += 1
                time.sleep(0.5)
            elif "dropbox" in title_lower and "dropbox" not in apps_to_launch_names_lower: # Close regular Dropbox windows if not launching
                console.log(f"[dim]Fechando janela regular do Dropbox:[/dim] {window.title}")
                window.close()
                closed_windows += 1
                time.sleep(0.5)
    except Exception as e:
        console.log(f"[{STYLE_ERROR}]Ocorreu um erro ao fechar as janelas: {e}[/{STYLE_ERROR}]")
    console.log(f"[bold green]{closed_windows} JANELAS FECHADAS.[/bold green]")

    # 4. LÓGICA PARA GARANTIR MINIMIZAÇÃO (EXISTENTE)
    minimized_windows = 0
    try:
        for window in gw.getAllWindows():
            # Força a minimização de apps específicos
            if "Steam" in window.title or "Profiler" in window.title:
                if window.isVisible:
                    console.log(f"[dim]Minimizando janela:[/dim] {window.title}")
                    window.minimize()
                    minimized_windows += 1
                    time.sleep(0.5)
    except Exception as e:
        console.log(f"[{STYLE_ERROR}]Ocorreu um erro ao minimizar janelas: {e}[/{STYLE_ERROR}]")
    console.log(f"[bold green]{minimized_windows} JANELAS MINIMIZADAS.[/bold green]")

# --- FUNÇÕES DE UI DO TERMINAL ---
# ... (RESTANTE DO CÓDIGO PERMANECE IGUAL)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_loading_spinner(text="CARREGANDO DADOS...", duration=1.5):
    clear_screen()
    with console.status(text, spinner="dots") as status:
        time.sleep(duration)

def type_text_effect(text, style):
    for char in text:
        console.print(char, end="", style=style)
        try: winsound.Beep(1400, 20)
        except Exception: pass
        time.sleep(0.025)
    console.print()
    time.sleep(0.5)

def crypto_animation(text_to_reveal):
    chars = string.ascii_uppercase + string.digits + "!@#$%^&*"
    result = [""] * len(text_to_reveal)
    with Live(console=console, auto_refresh=False) as live:
        for i in range(len(text_to_reveal)):
            if text_to_reveal[i] == " ":
                result[i] = " "
                continue
            for _ in range(5):
                scrambled_text = list(result)
                for j in range(i, len(text_to_reveal)):
                    if text_to_reveal[j] != " ":
                       scrambled_text[j] = random.choice(chars)
                live.update(Text("".join(scrambled_text), justify="center", style="bold cyan"), refresh=True)
                time.sleep(0.04)
            result[i] = text_to_reveal[i]
            live.update(Text("".join(result), justify="center", style="bold cyan"), refresh=True)
            time.sleep(0.05)

def show_splash_screen():
    clear_screen()
    console.rule(style=STYLE_MATRIX)
    type_text_effect("LUMON INDUSTRIES.", style=STYLE_MATRIX)
    type_text_effect("CONECTANDO AO MAINFRAME...", style=STYLE_MATRIX)
    console.rule(style=STYLE_MATRIX)
    time.sleep(1)

def get_battery_status():
    try:
        battery = psutil.sensors_battery()
        if battery:
            percent = int(battery.percent)
            status = "CARREGANDO" if battery.power_plugged else "DESCARREGANDO"
            return f"{status}: {percent}" + "%"
        return "BATERIA N/A"
    except Exception:
        return "BATERIA N/A"

def show_header():
    clear_screen()
    battery_status = get_battery_status()
    top_bar = Table.grid(expand=True)
    top_bar.add_column()
    top_bar.add_column(justify="right")
    top_bar.add_row(Text("SYS_OK [/]", style=STYLE_ACCENT), Text(battery_status, style=STYLE_FG))
    console.print(top_bar)
    console.print(Panel(Text("SEVERANCE SYSTEM", justify="center", style="bold white"), style=STYLE_ACCENT, border_style=STYLE_ACCENT))

    config = load_config()
    active_mode = config.get('active_mode', 'NENHUM')
    console.print(Align.center(Text.from_markup(f"MODO ATIVO: [bold]{active_mode}[/bold]", style="dim")))

def show_main_menu():
    show_header()
    space_a = 1
    space_b = space_a - 1
    console.print("\n" * space_a)
    menu_options = [
        ("1", "INICIAR MODO DE TRABALHO"),
        ("2", "INICIAR MODO PESSOAL"),
        ("3", "CONSULTAR BANCO DE DADOS"),
        ("4", "ADICIONAR APP AO BANCO DE DADOS"),
        ("5", "EXCLUIR APP DO BANCO DE DADOS"),
        ("6", "LIMPAR CACHE E ARQUIVOS TEMPORÁRIOS"),
        ("7", "ADICIONAR PAPEL DE PAREDE"),
        ("8", "RESTAURAR AO PADRÃO"),
        ("9", "SAIR"),
    ]

    # Calculate max lengths for alignment
    max_num_len = max(len(f"[{num}]") for num, _ in menu_options)
    max_desc_len = max(len(desc) for _, desc in menu_options)
    
    # Fixed number of dots as per user's example
    fixed_dots_length = 19 

    formatted_lines = []
    for num, desc in menu_options:
        num_str = f"[{num}]"
        dots_str = '.' * fixed_dots_length
        desc_padded = desc.ljust(max_desc_len) # Pad description to its max length
        
        # Construct the line content with internal alignment
        line_content = f"{num_str}{dots_str} {desc_padded}"
        formatted_lines.append(line_content)

    menu_text = "\n".join(formatted_lines)

    console.print(Panel(Align.center(Text(menu_text)), title="MENU DE OPÇÕES", border_style=STYLE_FG, padding=(2, 4)))
    console.print("\n" * space_b)
    console.print(Align.center(Text("Created by Ericsson Cardoso", style="dim")))

def clear_system_junk(console):
    console.log("[bold yellow]LIMPANDO CACHE E ARQUIVOS TEMPORÁRIOS...[/bold yellow]")
    
    temp_dirs = [
        os.environ.get('TEMP'),  # User temp
        os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Temp') # System temp
    ]
    
    cleaned_count = 0
    for temp_dir in temp_dirs:
        if not temp_dir or not os.path.exists(temp_dir):
            continue
        
        try: # Added try-except for os.listdir
            for item_name in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item_name)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.remove(item_path)
                        cleaned_count += 1
                        console.log(f"[dim]Removido:[/dim] {item_path}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        cleaned_count += 1
                        console.log(f"[dim]Removido:[/dim] {item_path}")
                except PermissionError:
                    console.log(f"[{STYLE_ERROR}]PERMISSÃO NEGADA:[/{STYLE_ERROR}] {item_path}")
                except OSError as e:
                    console.log(f"[{STYLE_ERROR}]ERRO AO REMOVER:[/{STYLE_ERROR}] {item_path} - {e}")
        except PermissionError: # Catch PermissionError for os.listdir
            console.log(f"[{STYLE_ERROR}]PERMISSÃO NEGADA:[/{STYLE_ERROR}] Não foi possível listar o conteúdo de: {temp_dir}. Tente executar como administrador para limpar esta pasta.")
        except OSError as e:
            console.log(f"[{STYLE_ERROR}]ERRO AO ACESSAR:[/{STYLE_ERROR}] {temp_dir} - {e}")

    console.log(f"[bold green]{cleaned_count} ITENS TEMPORÁRIOS REMOVIDOS.[/bold green]")
    time.sleep(1)

def start_mode(mode_name, apps_to_launch, apps_to_terminate):
    show_loading_spinner(f"INICIANDO {mode_name}...")
    
    config = load_config()
    config['active_mode'] = mode_name # Save active mode
    save_config(config)

    wallpaper_data = None
    if mode_name == "TRABALHO":
        wallpaper_data = config.get('work_wallpaper')
    elif mode_name == "PESSOAL":
        wallpaper_data = config.get('personal_wallpaper')

    if wallpaper_data and wallpaper_data.get('path'):
        wallpaper_path = wallpaper_data['path']
        if not os.path.exists(wallpaper_path):
            console.log(f"[{STYLE_ERROR}]ERRO:[/{STYLE_ERROR}] Arquivo de papel de parede não encontrado: {wallpaper_path}")
            console.log(f"[{STYLE_ERROR}]AVISO:[/{STYLE_ERROR}] Papel de parede configurado para o modo {mode_name} não encontrado: {wallpaper_path}")
            time.sleep(2)
            return # Exit if file not found

        wallpaper_style_key = wallpaper_data.get('style', "1") # Default to Fill

        # Map style key to registry values
        style_map = {
            "1": {"WallpaperStyle": 10, "TileWallpaper": 0}, # Fill
            "2": {"WallpaperStyle": 6, "TileWallpaper": 0},  # Fit
            "3": {"WallpaperStyle": 2, "TileWallpaper": 0},  # Stretch
            "4": {"WallpaperStyle": 0, "TileWallpaper": 1},  # Tile
            "5": {"WallpaperStyle": 0, "TileWallpaper": 0},  # Center
            "6": {"WallpaperStyle": 22, "TileWallpaper": 0} # Span
        }
        
        style_values = style_map.get(wallpaper_style_key, style_map["1"]) # Default to Fill if key not found
        wallpaper_style = style_values["WallpaperStyle"]
        tile_wallpaper = style_values["TileWallpaper"]
        
        try:
            console.log(f"[dim]APLICANDO PAPEL DE PAREDE PARA O MODO {mode_name}...")
            
            # Set registry values for wallpaper style
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_DWORD, wallpaper_style)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_DWORD, tile_wallpaper)
            winreg.CloseKey(key)

            # Call SystemParametersInfo to set wallpaper
            # Ensure path uses backslashes and is absolute
            formatted_wallpaper_path = os.path.abspath(wallpaper_path).replace('/', '\\')
            ctypes.windll.user32.SystemParametersInfoW(20, 0, ctypes.c_wchar_p(formatted_wallpaper_path), 0x01 | 0x02)
            
            console.log(f"[bold green]PAPEL DE PAREDE APLICADO.[/bold green]")
        except Exception as e:
            console.log(f"[{STYLE_ERROR}]ERRO AO APLICAR PAPEL DE PAREDE:[/{STYLE_ERROR}] {e}")
    elif wallpaper_data and wallpaper_data.get('path'):
        console.log(f"[{STYLE_ERROR}]AVISO:[/{STYLE_ERROR}] Papel de parede configurado para o modo {mode_name} não encontrado: {wallpaper_data['path']}")
    else:
        console.log(f"[dim]Nenhum papel de parede configurado para o modo {mode_name}.[/dim]")

    with console.status("PROCESSANDO...", spinner="dots") as status:
        manage_processes(apps_to_launch, apps_to_terminate, status)
    

    
    console.print(f"\n[bold green]MODO {mode_name} ATIVADO COM SUCESSO.[/bold green]")
    time.sleep(3)



def view_database():
    show_loading_spinner()
    clear_screen()
    show_header()
    work_apps = load_apps(WORK_DB)
    personal_apps = load_apps(PERSONAL_DB)
    table = Table(title="BANCO DE DADOS DE APLICATIVOS", border_style=STYLE_ACCENT, show_lines=True)
    table.add_column("MODO DE TRABALHO", style=STYLE_FG, justify="left")
    table.add_column("MODO PESSOAL", style=STYLE_FG, justify="left")
    max_rows = max(len(work_apps), len(personal_apps))
    for i in range(max_rows):
        work_app_str = ""
        if i < len(work_apps): work_app_str = f"[bold]{work_apps[i]['name']}[/bold]\n[dim]{work_apps[i]['path']}[/dim]"
        personal_app_str = ""
        if i < len(personal_apps): personal_app_str = f"[bold]{personal_apps[i]['name']}[/bold]\n[dim]{personal_apps[i]['path']}[/dim]"
        table.add_row(work_app_str, personal_app_str)
    console.print(table)
    Prompt.ask("\nPressione [bold]Enter[/bold] para voltar ao menu")

def add_app_screen():
    while True:
        show_loading_spinner("INICIANDO INTERFACE DE ENTRADA...")
        clear_screen()
        show_header()
        console.print(Panel("[bold]ADICIONAR NOVO APLICATIVO[/bold]", border_style=STYLE_ACCENT))
        
        db_choice = Prompt.ask("Selecione o banco de dados", choices=["t", "p"], default="t")
        db_name = WORK_DB if db_choice.lower() == 't' else PERSONAL_DB
        app_name = Prompt.ask("NOME DO APP (ex: Notepad) ou digite [0] para voltar")
        if app_name == "0":
            console.print("\n[dim]Voltando ao menu principal...[/dim]")
            time.sleep(1)
            break

        console.print("Abrindo buscador de arquivos...", style="dim")
        app_path = ""
        try:
            # Hide the main Tkinter window
            root = tk.Tk()
            root.withdraw()

            app_filetypes = [("Executáveis", "*.exe"), ("VBScript", "*.vbs"), ("Todos os arquivos", "*.* אמיתי")]
            app_path = filedialog.askopenfilename(filetypes=app_filetypes)
            
            root.destroy() # Destroy the Tkinter root window

            if app_path:
                console.print(f"Caminho selecionado: [cyan]{app_path}[/cyan]")
            else:
                console.print(f"\n[{STYLE_ERROR}]Nenhum arquivo selecionado. Operação cancelada.[/{STYLE_ERROR}]")
                time.sleep(2)
                break # Exit the loop if no file was selected
        except Exception as e:
            console.log(f"[{STYLE_ERROR}]ERRO:[/{STYLE_ERROR}] Não foi possível abrir o buscador de arquivos: {e}")
            time.sleep(2)
            if not Confirm.ask("Tentar novamente?"):
                break
            continue
        if app_name and app_path:
            close_after_launch = Confirm.ask("Fechar janela após iniciar? (Serpro, RyzenTest, etc.)")
            apps = load_apps(db_name)
            apps.append({"name": app_name.upper(), "path": app_path, "close_after_launch": close_after_launch})
            save_apps(db_name, apps)
            console.print(f"\n[bold green]SUCESSO![/bold green] App '{app_name}' adicionado.")
        else:
            console.print(f"\n[{STYLE_ERROR}]ERRO:[/{STYLE_ERROR}] Nome e caminho não podem ser vazios.")
        time.sleep(2)

        if not Confirm.ask("Deseja adicionar outro aplicativo?"):
            break


def delete_app_screen():
    while True:
        show_loading_spinner("CONSULTANDO REGISTROS...")
        clear_screen()
        show_header()
        console.print(Panel("[bold]EXCLUIR APLICATIVO[/bold]", border_style=STYLE_ACCENT))
        db_choice = Prompt.ask("Selecione o banco de dados", choices=["t", "p"], default="t")
        db_name = WORK_DB if db_choice.lower() == 't' else PERSONAL_DB
        apps = load_apps(db_name)
        if not apps:
            console.print(f"\nO banco de dados {db_choice.upper()} está vazio.")
            time.sleep(2)
            break
        
        console.print("\n[bold]Aplicativos no banco de dados:[/bold]")
        for i, app in enumerate(apps):
            console.print(f"  [{i+1}] {app['name']}")
        
        while True:
            try:
                app_index = int(Prompt.ask("Digite o NÚMERO do app que deseja excluir ou digite [0] para voltar")) - 1
                if app_index == -1: # User entered 0
                    console.print("\n[dim]Voltando ao menu principal...[/dim]")
                    time.sleep(1)
                    break
                if 0 <= app_index < len(apps):
                    app_to_delete = apps[app_index]['name']
                    break
                else:
                    console.print(f"[{STYLE_ERROR}]Número inválido. Por favor, digite um número entre 1 e {len(apps)}.[/]{STYLE_ERROR}")
            except ValueError:
                console.print(f"[{STYLE_ERROR}]Entrada inválida. Por favor, digite um número.[/]{STYLE_ERROR}")
        else: # This else belongs to the inner while, if it breaks, we break outer while
            break

        if Confirm.ask(f"Tem certeza que deseja excluir '{app_to_delete}'?"):
            apps = [app for i, app in enumerate(apps) if i != app_index]
            save_apps(db_name, apps)
            console.print(f"\n[bold green]SUCESSO![/bold green] App '{app_to_delete}' excluído.")
        else:
            console.print("\nOperação cancelada.")
        time.sleep(2)

        if not Confirm.ask("Deseja excluir outro aplicativo?"):
            break


def add_wallpaper_screen():
    while True:
        show_loading_spinner("INICIANDO CONFIGURAÇÃO DE PAPEL DE PAREDE...")
        clear_screen()
        show_header()
        console.print(Panel("[bold]CONFIGURAR PAPEL DE PAREDE[/bold]", border_style=STYLE_ACCENT))
        
        mode_choice = Prompt.ask("Selecione o modo para configurar o papel de parede", choices=["t", "p"], default="t")
        mode_name = "TRABALHO" if mode_choice.lower() == 't' else "PESSOAL"

        console.print(f"Abrindo buscador de arquivos para o modo {mode_name}...")
        wallpaper_path = ""
        try:
            # Hide the main Tkinter window
            root = tk.Tk()
            root.withdraw()

            wallpaper_filetypes = [("Arquivos de Imagem", "*.png *.jpg *.jpeg"), ("Todos os arquivos", "*.* אמ")]
            wallpaper_path = filedialog.askopenfilename(filetypes=wallpaper_filetypes)
            
            root.destroy() # Destroy the Tkinter root window

            if wallpaper_path:
                console.print(f"Caminho selecionado: [cyan]{wallpaper_path}[/cyan]")
            else:
                console.print(f"\n[{STYLE_ERROR}]Nenhum arquivo selecionado. Operação cancelada.[/{STYLE_ERROR}]\n[dim]Voltando ao menu principal...[/dim]")
                time.sleep(2)
                break # Exit the loop if no file was selected
        except Exception as e:
            console.log(f"[{STYLE_ERROR}]ERRO:[/{STYLE_ERROR}] Não foi possível abrir o buscador de arquivos: {e}")
            time.sleep(2)
            if not Confirm.ask("Tentar novamente?"):
                break
            continue

        # Validate file extension
        _, ext = os.path.splitext(wallpaper_path)
        if ext.lower() not in ['.jpg', '.jpeg', '.png']:
            console.print(f"[{STYLE_ERROR}]ERRO:[/{STYLE_ERROR}] Formato de arquivo inválido. Apenas .jpg e .png são permitidos.")
            time.sleep(3)
            if not Confirm.ask("Tentar novamente?"):
                break
            continue

        # Prompt for wallpaper style
        style_choices = {
            "1": "Preencher (Fill)",
            "2": "Ajustar (Fit)",
            "3": "Esticar (Stretch)",
            "4": "Lado a Lado (Tile)",
            "5": "Centralizar (Center)",
            "6": "Span (Múltiplos Monitores)"
        }
        console.print("\n[bold]Selecione o estilo do papel de parede:[/bold]")
        for key, value in style_choices.items():
            console.print(f"  [{key}] {value}")
        
        selected_style_key = Prompt.ask("Escolha uma opção", choices=list(style_choices.keys()), default="1")
        selected_style_name = style_choices[selected_style_key]

        config = load_config()
        if mode_choice.lower() == 't':
            config['work_wallpaper'] = {"path": wallpaper_path, "style": selected_style_key}
        else:
            config['personal_wallpaper'] = {"path": wallpaper_path, "style": selected_style_key}
        save_config(config)
        
        console.print(f"\n[bold green]SUCESSO![/bold green] Papel de parede para o modo {mode_name} configurado como '{selected_style_name}'.")
        time.sleep(2)

        if not Confirm.ask("Deseja configurar outro papel de parede?"):
            break


def restore_to_default():
    show_loading_spinner("PREPARANDO PARA RESTAURAR PADRÕES...")
    clear_screen()
    show_header()
    console.print(Panel("[bold]RESTAURAR AO PADRÃO[/bold]", border_style=STYLE_ACCENT))
    
    if Confirm.ask("[bold red]ATENÇÃO:[/bold red] Esta ação irá apagar TODOS os dados (aplicativos e configurações) e restaurar o sistema ao seu estado inicial. Tem certeza que deseja continuar?"):
        try:
            if os.path.exists(get_db_path(WORK_DB)):
                os.remove(get_db_path(WORK_DB))
                console.log(f"[dim]Removido:[/dim] {WORK_DB}")
            if os.path.exists(get_db_path(PERSONAL_DB)):
                os.remove(get_db_path(PERSONAL_DB))
                console.log(f"[dim]Removido:[/dim] {PERSONAL_DB}")
            if os.path.exists(get_db_path(CONFIG_DB)):
                os.remove(get_db_path(CONFIG_DB))
                console.log(f"[dim]Removido:[/dim] {CONFIG_DB}")
            
            console.print("\n[bold green]SISTEMA RESTAURADO AO PADRÃO COM SUCESSO.[/bold green]")
            console.print("[dim]Por favor, reinicie o aplicativo para aplicar todas as mudanças.[/dim]")
            time.sleep(4)
            sys.exit() # Exit to force a clean restart
        except Exception as e:
            console.print(f"[{STYLE_ERROR}]ERRO AO RESTAURAR:[/{STYLE_ERROR}] {e}")
            time.sleep(3)
    else:
        console.print("\n[dim]Operação cancelada.[/dim]")
        time.sleep(2)


def main():
    os.system("title LUMON OS")
    show_splash_screen() # This now only shows LUMON INDUSTRIES... and CONECTANDO AO MAINFRAME...

    config = load_config()
    user_name = config.get("user_name")

    if not user_name:
        clear_screen()
        console.print(Align.center(Panel(Text("BEM-VINDO AO SISTEMA SEVERANCE", justify="center", style="bold white"), border_style="green")))
        console.print("\n")
        console.print(Align.center(Text("Qual é o seu nome, innie?"))) # Centered question
        user_name = Prompt.ask("") # Non-centered prompt, no title
        config["user_name"] = user_name.strip().title()
        save_config(config)
        
        # New sequence for first-time user
        console.rule(style=STYLE_MATRIX)
        type_text_effect("VERIFICANDO CREDENCIAIS...", style=STYLE_MATRIX)
        console.rule(style=STYLE_MATRIX)
        time.sleep(1)
        clear_screen()
        console.print(Panel(Text("ACESSO CONCEDIDO", justify="center", style="bold white"), border_style="green"))
        time.sleep(2)
        clear_screen() # Clear after animation
        crypto_animation("SEVERANCE SYSTEM")
        time.sleep(2)
        clear_screen() # Clear after animation
        console.print(Align.center(Panel(Text(f"Olá, {user_name.strip().title()}! Preparado para um novo dia?", justify="center", style="bold white"), border_style="green")))
        time.sleep(3)

    else: # Existing user
        console.print(Align.center(Panel(Text(f"Bem-vindo de volta, {user_name.strip().title()}!", justify="center", style="bold white"), border_style="green")))
        time.sleep(2)

    while True:
        show_main_menu()
        console.print(f"\n[{STYLE_ACCENT}]>>>[/{STYLE_ACCENT}] ", end="")
        choice = input()
        if choice == "1": start_mode("TRABALHO", load_apps(WORK_DB), load_apps(PERSONAL_DB))
        elif choice == "2": start_mode("PESSOAL", load_apps(PERSONAL_DB), load_apps(WORK_DB))
        elif choice == "3": view_database()
        elif choice == "4": add_app_screen()
        elif choice == "5": delete_app_screen()
        elif choice == "6": clear_system_junk(console)
        elif choice == "7": add_wallpaper_screen()
        elif choice == "8": restore_to_default()
        elif choice == "9": break # SAIR is now option 9
        else: console.print(f"\n[{STYLE_ERROR}]OPÇÃO INVÁLIDA.[/]\n"); time.sleep(1)

    clear_screen()
    console.print(Align.center(Panel(Text(f"Até logo, {user_name.strip().title()}! Tenha um bom dia.", justify="center", style="bold yellow"), border_style="yellow")))
    time.sleep(2)
    console.print("\nDESLIGANDO SISTEMA...", style="bold yellow")
    time.sleep(1)



if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print("\n\nDESLIGAMENTO DE EMERGÊNCIA INICIADO.", style="bold red")
        time.sleep(1)
