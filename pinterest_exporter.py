import os
import time
import subprocess
import shutil
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
import static_ffmpeg

# Initialisation de ffmpeg pour yt-dlp (gestion des vidéos)
static_ffmpeg.add_paths()

def resource_path(relative_path):
    """ Récupère le chemin absolu vers la ressource (pour PyInstaller) """
    try:
        # PyInstaller crée un dossier temporaire _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_tool_path(tool_name):
    """ Renvoie le chemin de l'outil (interne à l'EXE ou système) """
    internal_path = resource_path(f"{tool_name}.exe")
    if os.path.exists(internal_path):
        return internal_path
    return tool_name

def select_folder(default_path):
    """Ouvre une fenêtre de sélection de dossier."""
    root = tk.Tk()
    root.withdraw()  # Masque la fenêtre principale de Tkinter
    root.attributes('-topmost', True)  # Met la fenêtre au premier plan
    
    print("\n[Action] Une fenêtre vient de s'ouvrir pour choisir le dossier de sauvegarde...")
    folder_selected = filedialog.askdirectory(initialdir=default_path, title="Sélectionnez le dossier de téléchargement")
    root.destroy()
    
    if not folder_selected:
        print(f"[Info] Aucune sélection, utilisation du dossier par défaut : {default_path}")
        return default_path
    
    return os.path.abspath(folder_selected)

def main():
    print("=== Pinterest High-Res Downloader (Universal & Portable) ===\n")
    print("Ce script pilote 'gallery-dl' pour ranger chaque image dans son dossier respectif.")
    print("Il utilise les cookies de votre navigateur pour vous connecter.\n")

    # 1. Chargement de la config
    load_dotenv()
    username = os.getenv("PINTEREST_USERNAME")
    default_download_root = os.getenv("DOWNLOAD_PATH") or os.path.join(os.getcwd(), "downloads")
    default_browser = os.getenv("PINTEREST_BROWSER")

    if not username:
        username = input("Pinterest Username (ex: avlao) : ").strip()
    
    # Choix du dossier de destination
    download_root = select_folder(default_download_root)
    
    # Sélection du navigateur
    browsers = ["firefox", "chrome", "edge", "brave", "vivaldi", "opera", "chromium"]
    browser = default_browser
    if not browser or browser not in browsers:
        print("\nNavigateurs supportés : " + ", ".join(browsers))
        browser = input(f"Quel navigateur utilisez-vous ? [firefox] : ").strip().lower()
        if not browser:
            browser = "firefox"

    if not os.path.exists(download_root):
        os.makedirs(download_root)
    
    print(f"\n[Configuration Active]")
    print(f"  Cible      : https://fr.pinterest.com/{username}/")
    print(f"  Navigateur : {browser}")
    print(f"  Dossier    : {download_root}")
    
    # --- PHASE 1 : DÉCOUVERTE ---
    print("\n[Étape 1/3] Scan des tableaux pour trouver les URLs...")
    
    gallery_dl_path = get_tool_path("gallery-dl")
    
    discovery_cmd = [
        gallery_dl_path,
        "-j",
        "--cookies-from-browser", browser,
        "--terminate", "1", 
        f"https://fr.pinterest.com/{username}/"
    ]
    
    boards = []
    try:
        result = subprocess.run(discovery_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        output = result.stdout
        
        try:
            data = json.loads(output)
            items = []
            if isinstance(data, list):
                for outer in data:
                    if isinstance(outer, list):
                        items.extend(outer)
                    else:
                        items.append(outer)
            
            for item in items:
                if isinstance(item, dict) and item.get("type") == "board":
                    b_name = item.get("name")
                    b_url = item.get("url")
                    if b_name and b_url:
                        if b_url.startswith("/"):
                            b_url = f"https://fr.pinterest.com{b_url}"
                        boards.append({"name": b_name, "url": b_url})
        except json.JSONDecodeError:
            names = re.findall(r'"name":\s*"([^"]+)"', output)
            urls = re.findall(r'"url":\s*"(/[^"]+/)"', output)
            for n, u in zip(names, urls):
                boards.append({"name": n, "url": f"https://fr.pinterest.com{u}"})

    except Exception as e:
        print(f"\n[Erreur Critique] Impossible de lancer le scan : {e}")
        print("-" * 30)
        print("Causes possibles :")
        print(f"1. L'outil '{gallery_dl_path}' est introuvable.")
        print("2. Votre navigateur est ouvert (Windows bloque l'accès aux cookies).")
        print("3. Vous n'êtes pas connecté sur Pinterest dans ce navigateur.")
        print("-" * 30)
        input("\nAppuyez sur Entrée pour quitter...")
        return

    if not boards:
        print(f"[Erreur] Aucun tableau trouvé. Vérifiez votre pseudo ou votre connexion sur {browser}.")
        input("\nAppuyez sur Entrée pour quitter...")
        return

    print(f"[Succès] {len(boards)} tableaux identifiés.")

    # --- PHASE 2 & 3 : CRÉATION & TÉLÉCHARGEMENT ---
    print("\n[Étape 2 & 3] Création des dossiers et téléchargement séquentiel...")
    
    # On crée aussi un fichier archive.txt global dans le dossier choisi
    archive_file = os.path.join(download_root, "pinterest_archive.txt")

    for i, board in enumerate(boards, 1):
        b_name = board["name"]
        b_url = board["url"]
        
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", b_name)
        board_path = os.path.join(download_root, safe_name)
        
        if not os.path.exists(board_path):
            os.makedirs(board_path, exist_ok=True)
        
        print(f"\n[{i}/{len(boards)}] Tableau : {b_name}")
        
        cmd = [
            gallery_dl_path,
            "--cookies-from-browser", browser,
            "--directory", board_path,
            "--download-archive", archive_file,
            "--sleep", "3-6",
            "--sleep-request", "1-2",
            b_url
        ]
        
        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            print("\n[Arrêt] Interrompu par l'utilisateur.")
            break
        except Exception as e:
            print(f"  [Erreur] Echec sur ce tableau : {e}")

    print("\n=== OPÉRATION TERMINÉE ! ===")
    print(f"Vos fichiers sont disponibles ici : {download_root}")
    input("\nAppuyez sur Entrée pour quitter...")

if __name__ == "__main__":
    main()
