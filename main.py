"""Stock Review Alpha Assistant - Single-command launcher.

Starts both the FastAPI backend and the Vite frontend dev server.
Usage: python main.py
"""

import os
import shutil
import signal
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    backend_dir = os.path.join(PROJECT_ROOT, "backend")
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
    venv_uvicorn = os.path.join(backend_dir, "venv", "Scripts", "uvicorn.exe")

    if not os.path.exists(venv_uvicorn):
        venv_uvicorn = os.path.join(backend_dir, ".venv", "bin", "uvicorn")

    os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)

    print("=" * 50)
    print("Stock Review Alpha Assistant")
    print("=" * 50)

    # Start backend (output goes directly to terminal)
    backend_cmd = [
        venv_uvicorn,
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
    ]
    print("\n[Backend] http://localhost:8000")
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=backend_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    time.sleep(2)

    # Start frontend (output goes directly to terminal)
    npx_path = shutil.which("npx")
    frontend_cmd = [npx_path or "npx", "vite", "--host", "--port", "5173"]
    print("[Frontend] http://localhost:5173\n")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    print("-" * 50)
    print("Press Ctrl+C to stop both services")
    print("-" * 50 + "\n")

    def shutdown(signum=None, frame=None):
        print("\nShutting down...")
        if sys.platform == "win32":
            backend_proc.send_signal(signal.CTRL_BREAK_EVENT)
            frontend_proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            backend_proc.terminate()
            frontend_proc.terminate()
        backend_proc.wait(timeout=5)
        frontend_proc.wait(timeout=5)
        print("Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            if backend_proc.poll() is not None and frontend_proc.poll() is not None:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
