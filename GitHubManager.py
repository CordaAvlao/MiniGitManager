import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
import json
import threading
import urllib.request
import urllib.error
import base64
import datetime
import webbrowser
import fnmatch

# Configuration
CONFIG_FILE = "manager_config.json"
DEFAULT_REPO = "" # Example: "Owner/RepoName"

class GitIgnoreChecker:
    def __init__(self, root_path):
        self.root_path = root_path
        self.patterns = []
        self.load_gitignore()

    def load_gitignore(self):
        ignore_path = os.path.join(self.root_path, ".gitignore")
        if os.path.exists(ignore_path):
            try:
                with open(ignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Basic gitignore to glob conversion
                            pattern = line
                            if pattern.endswith('/'):
                                pattern = pattern[:-1]
                            self.patterns.append(pattern)
            except Exception as e:
                print(f"Error loading .gitignore: {e}")

    def is_ignored(self, rel_path):
        # rel_path should be relative to self.root_path
        # Use forward slashes for consistency in matching
        rel_path = rel_path.replace('\\', '/')
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]
            
        parts = rel_path.split('/')
        
        for pattern in self.patterns:
            # Check if any part of the path matches or the whole path matches
            # This is a simplified version of gitignore logic
            if fnmatch.fnmatch(rel_path, pattern) or \
               fnmatch.fnmatch(rel_path, f"{pattern}/*") or \
               any(fnmatch.fnmatch(p, pattern) for p in parts):
                return True
        return False

class ProgressFileWrapper:
    def __init__(self, fileobj, total_size, callback):
        self.fileobj = fileobj
        self.total_size = total_size
        self.callback = callback
        self.bytes_read = 0

    def read(self, size=-1):
        chunk = self.fileobj.read(size)
        if chunk:
            self.bytes_read += len(chunk)
            self.callback(self.bytes_read, self.total_size)
        return chunk

    def __len__(self):
        return self.total_size

class GitHubManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MiniGit Manager - Navigator")
        self.root.geometry("1200x800")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # State
        self.token = ""
        self.username = ""
        self.current_repo = "" # Format: Owner/Repo
        
        self.current_local_path = os.getcwd()
        self.current_remote_path = "" # Root
        
        self.remote_cache = [] # Cache of current remote folder items
        
        # Icons (Unicode fallback)
        self.ICON_FOLDER = "📁"
        self.ICON_FILE = "jq"
        
        # Load Config
        self.load_config()
        
        # UI
        self.create_header()
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tab_files = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_files, text=" 📂 File Manager ")
        self.create_file_manager_ui()
        
        self.tab_releases = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_releases, text=" 🚀 Release Manager ")
        self.create_release_manager_ui()
        
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def create_header(self):
        frame = tk.Frame(self.root, bg="#333", pady=10)
        frame.pack(fill=tk.X)
        
        tk.Label(frame, text="MiniGit", font=("Segoe UI", 14, "bold"), bg="#333", fg="white").pack(side=tk.LEFT, padx=10)
        
        # Grid layout for inputs
        input_frame = tk.Frame(frame, bg="#333")
        input_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(input_frame, text="Token:", bg="#333", fg="#aaa").grid(row=0, column=0, sticky="e", padx=2)
        self.token_entry = tk.Entry(input_frame, width=25, show="*")
        self.token_entry.insert(0, self.token)
        self.token_entry.grid(row=0, column=1)
        
        tk.Label(input_frame, text="Repo (Owner/Name):", bg="#333", fg="#aaa").grid(row=1, column=0, sticky="e", padx=2)
        self.repo_entry = tk.Entry(input_frame, width=25)
        self.repo_entry.insert(0, self.current_repo)
        self.repo_entry.grid(row=1, column=1)
        
        tk.Button(frame, text="CONNECT", bg="#007acc", fg="white", font=("Segoe UI", 9, "bold"), command=self.connect).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="+ NEW REPO", bg="#28a745", fg="white", font=("Segoe UI", 9, "bold"), command=self.create_new_repo).pack(side=tk.LEFT, padx=5)
        
        self.lbl_user_status = tk.Label(frame, text="Offline", bg="#333", fg="#999")
        self.lbl_user_status.pack(side=tk.RIGHT, padx=10)
        
        tk.Button(frame, text="Logout", bg="#555", fg="white", font=("Segoe UI", 8), command=self.logout).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(frame, text="?", width=3, bg="#444", fg="white", font=("Segoe UI", 8, "bold"), command=self.show_about).pack(side=tk.RIGHT, padx=2)
        tk.Button(frame, text="MyGitHub", bg="#444", fg="white", font=("Segoe UI", 8), command=self.open_my_github).pack(side=tk.RIGHT, padx=2)

    def create_file_manager_ui(self):
        # Paned Window (50/50 Split)
        self.paned = tk.PanedWindow(self.tab_files, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=4)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- LEFT: LOCAL ---
        left_frame = ttk.LabelFrame(self.paned, text=" Local Files ")
        self.paned.add(left_frame, width=500) # Initial width hint
        
        # Nav Bar Local
        nav_l = tk.Frame(left_frame)
        nav_l.pack(fill=tk.X, padx=2, pady=2)
        tk.Button(nav_l, text="⬆", command=self.go_up_local, width=3).pack(side=tk.LEFT)
        self.path_entry_local = tk.Entry(nav_l)
        self.path_entry_local.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.path_entry_local.bind("<Return>", lambda e: self.navigate_local(self.path_entry_local.get()))
        tk.Button(nav_l, text="GO", command=lambda: self.navigate_local(self.path_entry_local.get()), width=4).pack(side=tk.RIGHT)
        tk.Button(nav_l, text="⟳", command=self.refresh_local, width=3).pack(side=tk.RIGHT, padx=2)

        # Tree Local
        self.tree_local = ttk.Treeview(left_frame, columns=("size", "date"), show="tree headings")
        self.tree_local.heading("#0", text="Name")
        self.tree_local.heading("size", text="Size")
        self.tree_local.heading("date", text="Date")
        self.tree_local.column("#0", width=200)
        self.tree_local.column("size", width=60, anchor="e")
        self.tree_local.column("date", width=110)
        
        scroll_l = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_local.yview)
        self.tree_local.configure(yscrollcommand=scroll_l.set)
        
        self.tree_local.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_l.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_local.bind("<Double-1>", self.on_local_double_click)
        
        # --- RIGHT: REMOTE ---
        right_frame = ttk.LabelFrame(self.paned, text=" GitHub Remote ")
        self.paned.add(right_frame)
        
        # Nav Bar Remote
        nav_r = tk.Frame(right_frame)
        nav_r.pack(fill=tk.X, padx=2, pady=2)
        tk.Button(nav_r, text="⬆", command=self.go_up_remote, width=3).pack(side=tk.LEFT)
        self.path_label_remote = tk.Entry(nav_r, fg="blue") # Read-only-ish entry for copy paste
        self.path_label_remote.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(nav_r, text="⟳", command=self.refresh_remote, width=3).pack(side=tk.RIGHT)

        # Tree Remote
        self.tree_remote = ttk.Treeview(right_frame, columns=("type", "size", "date"), show="tree headings")
        self.tree_remote.heading("#0", text="Name")
        self.tree_remote.heading("type", text="Type")
        self.tree_remote.heading("size", text="Size")
        self.tree_remote.heading("date", text="Date")
        self.tree_remote.column("#0", width=200)
        self.tree_remote.column("type", width=60)
        self.tree_remote.column("size", width=60, anchor="e")
        self.tree_remote.column("date", width=110)

        scroll_r = ttk.Scrollbar(right_frame, orient="vertical", command=self.tree_remote.yview)
        self.tree_remote.configure(yscrollcommand=scroll_r.set)
        
        self.tree_remote.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_r.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_remote.bind("<Double-1>", self.on_remote_double_click)
        
        # --- BOTTOM ACTIONS (Global) ---
        bot_frame = tk.Frame(self.tab_files, pady=5)
        bot_frame.pack(fill=tk.X)
        
        tk.Button(bot_frame, text="⬆ UPLOAD to Current Remote Folder", bg="#4caf50", fg="white", 
                  command=self.upload_selection).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                  
        tk.Button(bot_frame, text="⬇ DOWNLOAD to Current Local Folder", bg="#2196f3", fg="white",
                  command=self.download_selection).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                  
        tk.Button(bot_frame, text="🗑 DELETE Remote File", bg="#ff5555", fg="white",
                  command=self.delete_remote).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Button(bot_frame, text="⚡ RESET HISTORY (Squash)", bg="#000000", fg="white",
                  command=self.reset_history).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def create_release_manager_ui(self):
        # Keep similar to before, just simpler structure
        self.tree_releases = ttk.Treeview(self.tab_releases, columns=("tag", "name", "date", "assets"), show="headings")
        self.tree_releases.heading("tag", text="Tag")
        self.tree_releases.heading("name", text="Name")
        self.tree_releases.heading("date", text="Date")
        self.tree_releases.heading("assets", text="Assets")
        self.tree_releases.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        btns = tk.Frame(self.tab_releases)
        btns.pack(fill=tk.X, padx=10)
        ttk.Button(btns, text="Refresh", command=self.refresh_releases).pack(side=tk.LEFT)
        ttk.Button(btns, text="Delete Selected", command=self.delete_release).pack(side=tk.LEFT, padx=5)
        
        # Creator
        grp = ttk.LabelFrame(self.tab_releases, text=" Publish Release ")
        grp.pack(fill=tk.X, padx=10, pady=10)
        
        f1 = tk.Frame(grp)
        f1.pack(fill=tk.X, pady=5)
        tk.Label(f1, text="Tag (vX.X):").pack(side=tk.LEFT)
        self.entry_tag = tk.Entry(f1, width=10)
        self.entry_tag.pack(side=tk.LEFT, padx=5)
        tk.Label(f1, text="Name:").pack(side=tk.LEFT)
        self.entry_rel_name = tk.Entry(f1, width=25)
        self.entry_rel_name.pack(side=tk.LEFT, padx=5)
        
        f2 = tk.Frame(grp)
        f2.pack(fill=tk.X, pady=5)
        tk.Label(f2, text="Asset (.exe):").pack(side=tk.LEFT)
        self.entry_asset = tk.Entry(f2, width=40)
        self.entry_asset.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(f2, text="Browse", command=self.browse_asset).pack(side=tk.LEFT)
        
        tk.Button(grp, text="PUBLISH", bg="#007acc", fg="white", command=self.publish_release).pack(fill=tk.X, padx=50, pady=5)
        
        # Progress Tracking UI
        self.progress_frame = tk.Frame(grp)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.progress_frame.pack_forget() # Hide initially
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill=tk.X)
        
        self.progress_label = tk.Label(self.progress_frame, text="0.0% | 0.0 KB/s | ETA: --:--", font=("Consolas", 9))
        self.progress_label.pack()

    # --- CORE LOGIC ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.token = data.get("token", "")
                    self.current_repo = data.get("repo", "")
            except: pass
            
    def save_config(self):
        self.token = self.token_entry.get().strip()
        self.current_repo = self.repo_entry.get().strip()
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"token": self.token, "repo": self.current_repo}, f)

    def logout(self):
        if messagebox.askyesno("Confirm", "Logout and clear config?"):
            self.token = ""
            self.current_repo = ""
            self.token_entry.delete(0, tk.END)
            self.repo_entry.delete(0, tk.END)
            if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
            self.lbl_user_status.config(text="Offline")

    def create_new_repo(self):
        # Ensure we have a token
        self.token = self.token_entry.get().strip()
        if not self.token:
            messagebox.showerror("Error", "Token required to create a repository!")
            return
        
        # Ask for repo name
        repo_name = simpledialog.askstring("New Repository", "Enter the name for your new repository:")
        if not repo_name:
            return
        
        # Ask for description (optional)
        description = simpledialog.askstring("Description", "Enter a description (optional):", initialvalue="")
        
        # Ask if private
        is_private = messagebox.askyesno("Visibility", "Make repository PRIVATE?\n\n(No = Public)")
        
        def _create():
            self.status_var.set(f"Creating repository '{repo_name}'...")
            try:
                data = {
                    "name": repo_name,
                    "description": description or "",
                    "private": is_private,
                    "auto_init": True  # Creates a README so it's not empty
                }
                
                url = "https://api.github.com/user/repos"
                req = urllib.request.Request(url, data=json.dumps(data).encode())
                req.add_header("Authorization", f"Bearer {self.token}")
                req.add_header("Content-Type", "application/json")
                req.add_header("Accept", "application/vnd.github.v3+json")
                
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode())
                    full_name = result['full_name']  # e.g. "CordaAvlao/NewRepo"
                    
                self.status_var.set(f"Repository '{repo_name}' created!")
                messagebox.showinfo("Success", f"Repository created!\n\n{full_name}\n\nIt will now be set as current repo.")
                
                # Auto-fill the repo entry and connect
                self.root.after(0, lambda: self._set_and_connect(full_name))
                
            except urllib.error.HTTPError as e:
                if e.code == 422:
                    self.status_var.set("Repository already exists!")
                    messagebox.showerror("Error", f"Repository '{repo_name}' already exists!")
                else:
                    self.status_var.set(f"Create failed: {e}")
            except Exception as e:
                self.status_var.set(f"Create failed: {e}")
                
        threading.Thread(target=_create, daemon=True).start()

    def _set_and_connect(self, full_name):
        self.repo_entry.delete(0, tk.END)
        self.repo_entry.insert(0, full_name)
        self.connect()

    def connect(self):
        self.save_config()
        if not self.token or not self.current_repo:
            messagebox.showerror("Error", "Token and Repo required!")
            return
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        self.status_var.set("Connecting...")
        try:
            # 1. Get User
            u = self.api_request("https://api.github.com/user")
            self.username = u['login']
            
            # 2. Check Repo existence
            self.api_request(f"https://api.github.com/repos/{self.current_repo}")
            
            self.root.after(0, lambda: self.lbl_user_status.config(text=f"Connected: {self.username}", fg="#00ff00"))
            self.status_var.set(f"Connected to {self.current_repo}")
            
            # Init Views
            self.root.after(0, self.refresh_local)
            self.root.after(0, self.refresh_remote)
            self.root.after(0, self.refresh_releases)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Conn Error", str(e)))
            self.status_var.set("Connection Failed.")

    def api_request(self, url, method="GET", data=None):
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        
        body = json.dumps(data).encode() if data else None
        
        with urllib.request.urlopen(req, data=body) as r:
            if method == "DELETE": return None
            return json.loads(r.read().decode())

    # --- LOCAL FILE LOGIC ---
    def refresh_local(self):
        self.path_entry_local.delete(0, tk.END)
        self.path_entry_local.insert(0, self.current_local_path)
        
        self.tree_local.delete(*self.tree_local.get_children())
        
        try:
            items = os.listdir(self.current_local_path)
            # Sort: Folders first
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(self.current_local_path, x)), x.lower()))
            
            for item in items:
                path = os.path.join(self.current_local_path, item)
                is_dir = os.path.isdir(path)
                
                name_disp = f"📁 {item}" if is_dir else f"📄 {item}"
                if is_dir:
                    size = ""
                    dt = ""
                else:
                    size = f"{os.path.getsize(path)/1024:.1f} KB"
                    dt = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
                    
                self.tree_local.insert("", "end", text=name_disp, values=(size, dt), tags=("dir" if is_dir else "file", path))
                
        except Exception as e:
            self.status_var.set(f"Local Error: {e}")

    def navigate_local(self, path):
        if os.path.exists(path) and os.path.isdir(path):
            self.current_local_path = os.path.abspath(path)
            self.refresh_local()

    def go_up_local(self):
        parent = os.path.dirname(self.current_local_path)
        self.navigate_local(parent)

    def on_local_double_click(self, event):
        sel = self.tree_local.selection()
        if not sel: return
        item = self.tree_local.item(sel[0])
        if "dir" in item['tags']:
            path = item['tags'][1]
            self.navigate_local(path)

    # --- REMOTE FILE LOGIC ---
    def refresh_remote(self):
        if not self.token: return
        threading.Thread(target=self._remote_list_thread, daemon=True).start()

    def _remote_list_thread(self):
        self.status_var.set("Fetching remote...")
        try:
            # Clean path for display
            display_path = self.current_remote_path if self.current_remote_path else "(root)"
            self.root.after(0, lambda: self.path_label_remote.delete(0, tk.END) or self.path_label_remote.insert(0, display_path))
            
            url = f"https://api.github.com/repos/{self.current_repo}/contents/{self.current_remote_path}"
            data = self.api_request(url)
            
            if not isinstance(data, list): data = [data] # Single file case (shouldn't happen with nav logic)
            
            # Sort folders first
            data.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
            
            self.root.after(0, lambda: self._populate_remote(data))
            self.status_var.set("Remote OK.")
        except Exception as e:
            self.status_var.set(f"Remote Error: {e}")

    def _populate_remote(self, items):
        self.tree_remote.delete(*self.tree_remote.get_children())
        self.remote_cache = items
        
        # Store iids to update them later
        self.remote_item_map = {} # path -> iid
        
        for item in items:
            is_dir = (item['type'] == 'dir')
            name_disp = f"📁 {item['name']}" if is_dir else f"📄 {item['name']}"
            size = "" if is_dir else f"{item['size']/1024:.1f} KB"
            
            iid = self.tree_remote.insert("", "end", text=name_disp, values=(item['type'], size, "..."), tags=(item['type'], item['path'], item['name']))
            self.remote_item_map[item['path']] = iid
            
        # Start background date fetch
        threading.Thread(target=self._fetch_remote_dates, args=(items,), daemon=True).start()

    def _fetch_remote_dates(self, items):
        try:
            for item in items:
                # Get last commit for this file/folder
                url = f"https://api.github.com/repos/{self.current_repo}/commits?path={item['path']}&per_page=1"
                try:
                    res = self.api_request(url)
                    if res and len(res) > 0:
                        date_str = res[0]['commit']['committer']['date']
                        # Format date: 2025-12-14T... -> 2025-12-14 10:00
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
                        formatted = dt.strftime("%Y-%m-%d %H:%M")
                        
                        iid = self.remote_item_map.get(item['path'])
                        if iid:
                            # Update the treeview row
                            # We need to preserve other values. Treeview set can update one col?
                            # Yes, set(item, column, value)
                            self.root.after(0, lambda i=iid, v=formatted: self._safe_tree_update(i, "date", v))
                except Exception as e:
                    print(f"Date fetch error for {item['name']}: {e}")
                    
        except Exception as e:
            print(f"Date fetch loop error: {e}")

    def _safe_tree_update(self, iid, col, val):
        try:
            if self.tree_remote.exists(iid):
                self.tree_remote.set(iid, col, val)
        except: pass

    def go_up_remote(self):
        if not self.current_remote_path: return # Already root
        # split by / and remove last
        parts = self.current_remote_path.split('/')
        if len(parts) <= 1:
            self.current_remote_path = ""
        else:
            self.current_remote_path = "/".join(parts[:-1])
        self.refresh_remote()

    def on_remote_double_click(self, event):
        sel = self.tree_remote.selection()
        if not sel: return
        item = self.tree_remote.item(sel[0])
        if item['values'][0] == 'dir':
            # It's a directory
            # Tag 1 is full path
            self.current_remote_path = item['tags'][1]
            self.refresh_remote()

    # --- ACTIONS ---
    def delete_remote(self):
        sel = self.tree_remote.selection()
        if not sel: return
        
        items_to_delete = []
        for s in sel:
            item_vals = self.tree_remote.item(s)
            t_type = item_vals['tags'][0]
            t_path = item_vals['tags'][1]
            t_name = item_vals['tags'][2]
            
            # For file delete we need SHA. 
            t_sha = next((x['sha'] for x in self.remote_cache if x['path'] == t_path), None)
            
            items_to_delete.append({
                "type": t_type,
                "path": t_path,
                "name": t_name,
                "sha": t_sha
            })
            
        count = len(items_to_delete)
        if count == 0: return
        
        if count > 1:
            if not messagebox.askyesno("Delete Multiple", f"⚠️ DANGER: Delete {count} items?\n\nIncludes folders which will be recursively deleted.\nThis cannot be undone."): return
        else:
             # Single item checks
             it = items_to_delete[0]
             if it['type'] == 'dir':
                  if not messagebox.askyesno("Recursive Delete", f"⚠️ DANGER: Delete folder '{it['name']}' and ALL its contents?\n\nThis cannot be undone."): return
             else:
                  if not messagebox.askyesno("Delete", f"Delete remote file '{it['name']}'?"): return

        threading.Thread(target=self._delete_items_thread, args=(items_to_delete,), daemon=True).start()

    def _delete_items_thread(self, items):
        self.status_var.set(f"Deleting {len(items)} items...")
        total = 0
        errors = 0
        
        try:
            for item in items:
                if item['type'] == 'dir':
                    c, e = self._delete_folder_recursive_sync(item['path'])
                    total += c
                    errors += e
                else:
                    try:
                        self.status_var.set(f"Deleting {item['name']}...")
                        self._delete_file_sync(item['path'], item['sha'], item['name'])
                        total += 1
                    except Exception as e:
                        print(f"Failed to delete {item['name']}: {e}")
                        errors += 1
                        
            self.root.after(0, self.refresh_remote)
            self.status_var.set(f"Deleted {total} files. Errors: {errors}")
            if total > 0 or errors > 0:
                 self.root.after(0, lambda: messagebox.showinfo("Deleted", f"Deletion Complete.\nFiles Deleted: {total}\nErrors: {errors}"))
                 
        except Exception as e:
            self.status_var.set(f"Batch Delete Error: {e}")

    def _delete_file_sync(self, path, sha, name):
         if not sha: raise Exception("Missing SHA")
         data = {"message": f"Delete {name}", "sha": sha}
         url = f"https://api.github.com/repos/{self.current_repo}/contents/{path}"
         
         req = urllib.request.Request(url, method="DELETE", data=json.dumps(data).encode())
         req.add_header("Authorization", f"Bearer {self.token}")
         urllib.request.urlopen(req)

    def _delete_folder_recursive_sync(self, folder_path):
        self.status_var.set(f"Scanning {folder_path}...")
        count = 0
        errors = 0
        try:
            # 1. Get contents
            url = f"https://api.github.com/repos/{self.current_repo}/contents/{folder_path}"
            items = self.api_request(url)
            if not isinstance(items, list): items = [items]
            
            for item in items:
                if item['type'] == 'dir':
                    c, e = self._delete_folder_recursive_sync(item['path'])
                    count += c
                    errors += e
                else:
                    self.status_var.set(f"Deleting {item['name']}...")
                    try:
                        self._delete_file_sync(item['path'], item['sha'], item['name'])
                        count += 1
                    except Exception as e:
                        print(e)
                        errors += 1
            return count, errors
            
        except Exception as e:
            print(f"Recursive Delete Error: {e}")
            return count, errors + 1

    def upload_selection(self):
        sel = self.tree_local.selection()
        if not sel: return
        
        # Gather all selected paths
        items_to_upload = []
        gitignore_path = None
        
        for s in sel:
            path = self.tree_local.item(s)['tags'][1]
            if os.path.basename(path) == ".gitignore":
                gitignore_path = path
            else:
                items_to_upload.append(path)
                
        # Prioritize .gitignore
        if gitignore_path:
            items_to_upload.insert(0, gitignore_path)
            
        count = len(items_to_upload)
        if count > 1:
            if not messagebox.askyesno("Upload Multiple", f"Upload {count} items?"): return
            
        # If single folder, ask recursive (legacy behavior preservation mostly)
        if count == 1 and os.path.isdir(items_to_upload[0]):
             if not messagebox.askyesno("Upload Folder", f"Upload folder '{os.path.basename(items_to_upload[0])}' and all contents?"): return

        threading.Thread(target=self._upload_items_thread, args=(items_to_upload,), daemon=True).start()

    def _upload_items_thread(self, paths):
        total_files = 0
        total_errors = 0
        skipped = 0
        
        # Initialize GitIgnoreChecker from current local path
        checker = GitIgnoreChecker(self.current_local_path)
        
        self.status_var.set(f"Starting upload of {len(paths)} items...")
        
        try:
            for path in paths:
                fname = os.path.basename(path)
                
                # Check if ignored (only if it's not the .gitignore itself)
                if fname != ".gitignore" and checker.is_ignored(fname):
                    print(f"Skipping ignored item: {fname}")
                    skipped += 1
                    continue

                if os.path.isdir(path):
                    f_count, f_err, f_skip = self._upload_folder_recursive_sync(path, checker)
                    total_files += f_count
                    total_errors += f_err
                    skipped += f_skip
                else:
                    # Single file
                    # Use current remote directory
                    remote_full_path = f"{self.current_remote_path}/{fname}" if self.current_remote_path else fname
                    self.status_var.set(f"Uploading {fname}...")
                    try:
                        self._upload_file(path, remote_full_path)
                        total_files += 1
                    except Exception as e:
                        print(f"Error uploading {fname}: {e}")
                        total_errors += 1
            
            self.root.after(0, self.refresh_remote)
            msg = f"Upload Complete.\nFiles: {total_files}\nErrors: {total_errors}\nIgnored: {skipped}"
            self.status_var.set(f"Uploaded {total_files} files. Errors: {total_errors}. Ignored: {skipped}")
            # Only show box if reasonable amount or errors
            if total_files > 0 or total_errors > 0:
                 self.root.after(0, lambda: messagebox.showinfo("Done", msg))
                 
        except Exception as e:
            self.status_var.set(f"Upload Batch Error: {e}")

    def _upload_folder_recursive_sync(self, local_folder, checker):
        # Sync version of recursive upload, returns (count, errors, skipped)
        base_name = os.path.basename(local_folder)
        remote_base = f"{self.current_remote_path}/{base_name}" if self.current_remote_path else base_name
        
        count = 0
        errors = 0
        skipped = 0
        
        for root, dirs, files in os.walk(local_folder):
            # rel_dir is relative to the folder where .gitignore is (self.current_local_path)
            rel_root = os.path.relpath(root, self.current_local_path)
            
            # Filter directories in-place for os.walk
            dirs[:] = [d for d in dirs if not checker.is_ignored(os.path.join(rel_root, d))]
            # We don't count skipped dirs here because they are not files, 
            # but their contents will be skipped.

            for file in files:
                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, self.current_local_path)
                
                if checker.is_ignored(rel_path):
                    print(f"Skipping ignored file: {rel_path}")
                    skipped += 1
                    continue

                # Remote path relative to current_remote_path
                # We need rel path from local_folder to preserve subfolder structure
                rel_from_folder = os.path.relpath(local_path, local_folder)
                remote_path = f"{remote_base}/{rel_from_folder}".replace("\\", "/")
                
                self.status_var.set(f"Uploading {file}...")
                try:
                    self._upload_file(local_path, remote_path)
                    count += 1
                except Exception as ex:
                    print(ex)
                    errors += 1
        return count, errors, skipped

    def _upload_file(self, local_path, remote_path):
        # Helper to upload one file (no threading spawn here, logic only)
        # Check SHA first to see if update
        sha = None
        # This check against cache is only valid for current view, but for recursive uploads
        # inside subfolders, our cache (self.remote_cache) is useless (it only has current level).
        # So for folder upload, we blindly overwrite or we should check existence.
        # To keep it fast/simple: Try GET first to get SHA? Or just PUT?
        # PUT requires SHA if file exists. So we MUST Get.
        
        # 1. Get SHA if exists
        try:
           url = f"https://api.github.com/repos/{self.current_repo}/contents/{remote_path}"
           res = self.api_request(url)
           sha = res['sha']
        except: 
           pass # File likely doesn't exist
           
        # 2. Upload
        with open(local_path, 'rb') as f: content = f.read()
        b64 = base64.b64encode(content).decode()
        
        data = {"message": f"Upload {os.path.basename(local_path)}", "content": b64}
        if sha: data["sha"] = sha
        
        url = f"https://api.github.com/repos/{self.current_repo}/contents/{remote_path}"
        self.api_request(url, "PUT", data)

    def reset_history(self):
        if not messagebox.askyesno("DANGER", "⚡ RESET HISTORY?\n\nThis will:\n1. Keep all current files exactly as they are.\n2. DELETE all previous commit history.\n3. Create a single fresh commit (v1.0).\n\nAre you sure?"): return
        
        def _reset():
            self.status_var.set("Reseting History...")
            try:
                # 1. Get current Head Commit
                ref = self.api_request(f"https://api.github.com/repos/{self.current_repo}/git/refs/heads/main")
                latest_commit_sha = ref['object']['sha']
                
                # 2. Get Tree of that commit
                commit = self.api_request(f"https://api.github.com/repos/{self.current_repo}/git/commits/{latest_commit_sha}")
                tree_sha = commit['tree']['sha']
                
                # 3. Create NEW Orphan Commit (No parents)
                data = {
                    "message": "Reset History (Clean Slate)",
                    "tree": tree_sha,
                    "parents": [] 
                }
                new_commit = self.api_request(f"https://api.github.com/repos/{self.current_repo}/git/commits", "POST", data)
                new_sha = new_commit['sha']
                
                # 4. Force Update Ref
                ref_data = {"sha": new_sha, "force": True}
                self.api_request(f"https://api.github.com/repos/{self.current_repo}/git/refs/heads/main", "PATCH", ref_data)
                
                self.status_var.set("History Reset Successful!")
                messagebox.showinfo("Success", "History has been reset to a single commit.")
                self.root.after(0, self.refresh_remote)
                
            except Exception as e:
                self.status_var.set(f"Reset Failed: {e}")
                
        threading.Thread(target=_reset, daemon=True).start()

    def download_selection(self):
        sel = self.tree_remote.selection()
        if not sel: return
        
        item = self.tree_remote.item(sel[0])
        if item['values'][0] == 'dir': return
        
        r_path = item['tags'][1]
        name = item['tags'][2]
        
        save_path = os.path.join(self.current_local_path, name)
        
        if os.path.exists(save_path):
            if not messagebox.askyesno("Overwrite", f"File '{name}' exists locally. Overwrite?"): return
            
        def _down():
            try:
                # Get Blob URL/Content
                url = f"https://api.github.com/repos/{self.current_repo}/contents/{r_path}"
                res = self.api_request(url) # This returns content in base64
                
                content = base64.b64decode(res['content'])
                with open(save_path, 'wb') as f:
                    f.write(content)
                    
                self.root.after(0, self.refresh_local)
                self.status_var.set(f"Downloaded {name}")
            except Exception as e:
                self.status_var.set(f"Download error: {e}")

        threading.Thread(target=_down, daemon=True).start()

    # --- RELEASES ---
    def refresh_releases(self):
        if not self.token: return
        threading.Thread(target=self._releases_thread, daemon=True).start()
        
    def _releases_thread(self):
        try:
            res = self.api_request(f"https://api.github.com/repos/{self.current_repo}/releases")
            self.root.after(0, lambda: self._populate_releases(res))
        except: pass

    def _populate_releases(self, releases):
        self.tree_releases.delete(*self.tree_releases.get_children())
        for r in releases:
            assets = ", ".join([a['name'] for a in r['assets']])
            self.tree_releases.insert("", "end", values=(r['tag_name'], r['name'], r['published_at'].split('T')[0], assets), tags=(r['id'],))

    def delete_release(self):
        sel = self.tree_releases.selection()
        if not sel: return
        id_ = self.tree_releases.item(sel[0])['tags'][0]
        
        def _del():
            try:
                self.api_request(f"https://api.github.com/repos/{self.current_repo}/releases/{id_}", "DELETE")
                self.root.after(0, self.refresh_releases)
            except Exception as e:
                print(e)
        threading.Thread(target=_del, daemon=True).start()

    def browse_asset(self):
        f = filedialog.askopenfilename()
        if f:
            self.entry_asset.delete(0, tk.END)
            self.entry_asset.insert(0, f)

    def publish_release(self):
        tag = self.entry_tag.get().strip()
        asset_path = self.entry_asset.get().strip()
        name = self.entry_rel_name.get().strip() or f"Release {tag}"
        
        if not tag: return
        
        def _pub():
            try:
                self.status_var.set(f"Checking release {tag}...")
                
                # 1. Try to create the release
                data = {"tag_name": tag, "name": name, "body": "Published via MiniGit Manager"}
                try:
                    res = self.api_request(f"https://api.github.com/repos/{self.current_repo}/releases", "POST", data)
                except urllib.error.HTTPError as e:
                    if e.code == 422:
                        # Release already exists?
                        if messagebox.askyesno("Release Exists", f"Release with tag '{tag}' already exists. Update it?"):
                            # Find the existing release ID
                            res = self._get_release_by_tag(tag)
                            if not res:
                                self.status_var.set("Error: Could not find existing release.")
                                return
                        else:
                            self.status_var.set("Publication cancelled.")
                            return
                    else:
                        raise e
                
                release_id = res['id']
                upload_url_raw = res['upload_url'].split('{')[0]
                
                # 2. Upload Asset
                if asset_path and os.path.exists(asset_path):
                    fname = os.path.basename(asset_path)
                    
                    # Check if asset already exists in this release
                    assets = res.get('assets', [])
                    for a in assets:
                        if a['name'] == fname:
                            self.status_var.set(f"Removing existing asset {fname}...")
                            self.api_request(f"https://api.github.com/repos/{self.current_repo}/releases/assets/{a['id']}", "DELETE")
                            break
                    
                    self.status_var.set(f"Uploading asset {fname}...")
                    
                    up_url = upload_url_raw + f"?name={fname}"
                    
                    # Streaming upload with Progress Tracking
                    file_size = os.path.getsize(asset_path)
                    start_time = datetime.datetime.now()
                    
                    self.root.after(0, lambda: self.progress_frame.pack(fill=tk.X, padx=10, pady=5))
                    
                    def progress_cb(bytes_read, total):
                        elapsed = (datetime.datetime.now() - start_time).total_seconds()
                        percent = (bytes_read / total) * 100
                        speed = bytes_read / elapsed if elapsed > 0 else 0
                        eta = (total - bytes_read) / speed if speed > 0 else 0
                        
                        speed_mb = speed / (1024 * 1024)
                        eta_str = str(datetime.timedelta(seconds=int(eta)))
                        status_text = f"{percent:.1f}% | {speed_mb:.2f} MB/s | ETA: {eta_str}"
                        
                        self.root.after(0, lambda: [
                            self.progress_bar.configure(value=percent),
                            self.progress_label.configure(text=status_text)
                        ])

                    with open(asset_path, 'rb') as f:
                        wrapped_file = ProgressFileWrapper(f, file_size, progress_cb)
                        req = urllib.request.Request(up_url, data=wrapped_file, method="POST")
                        req.add_header("Authorization", f"Bearer {self.token}")
                        req.add_header("Content-Type", "application/octet-stream")
                        req.add_header("Content-Length", str(file_size))
                        
                        with urllib.request.urlopen(req) as response:
                            response.read()
                    
                    self.root.after(0, self.progress_frame.pack_forget)
                
                self.root.after(0, self.refresh_releases)
                self.status_var.set("Release Published/Updated!")
                
            except Exception as e:
                self.root.after(0, self.progress_frame.pack_forget)
                self.status_var.set(f"Release Error: {e}")
                
        threading.Thread(target=_pub, daemon=True).start()

    def _get_release_by_tag(self, tag):
        # Fetch release details by tag
        try:
            return self.api_request(f"https://api.github.com/repos/{self.current_repo}/releases/tags/{tag}")
        except:
            return None

    def open_my_github(self):
        webbrowser.open("https://github.com/CordaAvlao")

    def show_about(self):
        messagebox.showinfo("About", "MiniGitManager V1.6\nMade by CordaAvlao\n23/12/2025")

if __name__ == "__main__":
    app = GitHubManager()
    app.root.mainloop()
