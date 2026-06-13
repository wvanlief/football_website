import sys
import subprocess

def install_dependencies():
    print("Checking dependencies...")
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import dotenv
        import tzdata
        print("All dependencies are already installed.")
    except ImportError:
        print("Missing dependencies. Installing from requirements.txt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            sys.exit(1)

def run_server():
    import os
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    # Default to True locally, but can be disabled in prod
    reload = os.getenv("RELOAD", "True").lower() in ("true", "1", "yes")

    print("\n" + "="*50)
    print(" STARTING FINDFOOTBALL.GAMES WATCHABILITY ENGINE & WEBSITE")
    print(f" Access the application at: http://{host}:{port}")
    print("="*50 + "\n")
    
    # Run uvicorn server
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    install_dependencies()
    run_server()
