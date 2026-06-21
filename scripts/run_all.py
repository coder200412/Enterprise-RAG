"""
Launch script — starts Ollama, FastAPI, and Streamlit together.
"""
import subprocess
import sys
import time
import os
import urllib.request
import json

# Set the working directory to project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT_DIR)


def check_ollama_running():
    """Check if Ollama is already running and responsive."""
    try:
        with urllib.request.urlopen("http://localhost:11434/", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def verify_models():
    """Check that the required models are available in Ollama."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            models = [m.get("name", "") for m in data.get("models", [])]
            model_names = [m.split(":")[0] for m in models]

            required = ["phi3", "nomic-embed-text"]
            missing = [r for r in required if r not in model_names]

            if missing:
                print(f"[!] Missing models: {missing}")
                print(f"[*] Available models: {models}")
                for m in missing:
                    print(f"[*] Pulling {m}... (this may take a few minutes)")
                    subprocess.run(
                        ["ollama", "pull", m],
                        timeout=600,
                    )
            else:
                print(f"[OK] Required models available: {models}")
            return True
    except Exception as e:
        print(f"[!] Could not verify models: {e}")
        return False


def setup_ollama():
    print("=" * 60)
    print("  [*] Configuring Ollama in CPU-only mode")
    print("=" * 60)

    # Set CPU-only env variables
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    os.environ["OLLAMA_LLM_LIBRARY"] = "cpu"
    os.environ["OLLAMA_VULKAN"] = "0"
    os.environ["GGML_VK_VISIBLE_DEVICES"] = "-1"
    os.environ["OLLAMA_NUM_PARALLEL"] = "4"

    # Check if Ollama is already running
    if check_ollama_running():
        print("[OK] Ollama is already running on port 11434!")
        verify_models()
        return True

    # Kill stale Ollama processes
    print("[*] Terminating any stale Ollama instances...")
    try:
        subprocess.run(["taskkill", "/F", "/T", "/IM", "ollama.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/T", "/IM", "ollama app.exe"], capture_output=True)
        time.sleep(1.5)
    except Exception:
        pass

    # Find ollama executable
    ollama_path = "ollama"
    default_windows_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if os.path.exists(default_windows_path):
        ollama_path = default_windows_path
    else:
        # Check if ollama is on PATH
        try:
            result = subprocess.run(["where", "ollama"], capture_output=True, text=True)
            if result.returncode != 0:
                print("=" * 60)
                print("  [ERROR] Ollama not found!")
                print("  Please install Ollama from: https://ollama.com/download")
                print("  After installing, restart this script.")
                print("=" * 60)
                return False
        except Exception:
            pass

    print(f"[*] Starting Ollama from: {ollama_path}")
    env = os.environ.copy()

    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW

        # Start Ollama serve (log to file for debugging)
        log_path = os.path.join(ROOT_DIR, "data", "ollama.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_file = open(log_path, "w")

        subprocess.Popen(
            [ollama_path, "serve"],
            env=env,
            creationflags=creationflags,
            stdout=log_file,
            stderr=log_file,
        )
    except Exception as e:
        print(f"[!] Failed to start Ollama: {e}")
        print("[!] Please start Ollama manually:")
        print("    1. Set environment: set OLLAMA_LLM_LIBRARY=cpu")
        print("    2. Run: ollama serve")
        return False

    # Poll Ollama until it's ready (up to 30 seconds)
    print("[*] Waiting for Ollama to start on port 11434...")
    for i in range(30):
        if check_ollama_running():
            print("[OK] Ollama is ready!")
            verify_models()
            return True
        time.sleep(1)
        if i % 5 == 4:
            print(f"    ... still waiting ({i+1}s)")

    print("=" * 60)
    print("  [ERROR] Ollama did not start!")
    print(f"  Check log at: {log_path}")
    print("  You can also start it manually:")
    print("    set OLLAMA_LLM_LIBRARY=cpu")
    print("    ollama serve")
    print("=" * 60)
    return False


def kill_ports():
    """Kill any stale processes on ports 8000 and 8501."""
    print("[*] Clearing ports 8000 and 8501...")
    for port in [8000, 8501]:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                 f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
    time.sleep(1)


def main():
    # Setup Ollama in CPU mode
    ollama_ok = setup_ollama()
    if not ollama_ok:
        print("\n[!] Continuing without Ollama — uploads and chat will NOT work.")
        print("[!] Please start Ollama manually and restart the app.\n")

    print("\n" + "=" * 60)
    print("  [*] Enterprise RAG - Starting Services")
    print("=" * 60)

    kill_ports()

    # Start FastAPI
    print("\n[*] Starting FastAPI backend on http://localhost:8000 ...")
    fastapi_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=ROOT_DIR,
    )
    time.sleep(3)

    # Start Streamlit
    print("[*] Starting Streamlit frontend on http://localhost:8501 ...")
    streamlit_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app/app.py", "--server.port", "8501"],
        cwd=ROOT_DIR,
    )

    print("\n" + "=" * 60)
    print("  [OK] Services Running!")
    print("  -> Ollama:    http://localhost:11434 " + ("(running)" if ollama_ok else "(NOT RUNNING)"))
    print("  -> API:       http://localhost:8000/docs")
    print("  -> Frontend:  http://localhost:8501")
    print("  Press Ctrl+C to stop all services")
    print("=" * 60 + "\n")

    try:
        fastapi_process.wait()
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down services...")
        fastapi_process.terminate()
        streamlit_process.terminate()
        fastapi_process.wait()
        streamlit_process.wait()

        print("[*] Stopping background Ollama service...")
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", "ollama.exe"], capture_output=True)
        except Exception:
            pass

        print("[*] All services stopped.")


if __name__ == "__main__":
    main()
