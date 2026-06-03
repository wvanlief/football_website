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
    print("\n" + "="*50)
    print(" STARTING MATCHWATCH WATCHABILITY ENGINE & WEBSITE")
    print(" Access the application at: http://localhost:8000")
    print("="*50 + "\n")
    
    import uvicorn
    # Run uvicorn server
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    install_dependencies()
    run_server()
