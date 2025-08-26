"""
Smart Notes API Setup Script
Quick setup and testing utilities
"""
import os
import sys
import subprocess
from pathlib import Path


def create_env_file():
    """Create .env file from template"""
    env_template = """# Smart Notes API Configuration
# IMPORTANT: Change SECRET_KEY in production!

API_HOST=127.0.0.1
API_PORT=8000
DEBUG=True
ENVIRONMENT=development

SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

ALLOWED_ORIGINS=["http://localhost:3000", "chrome-extension://*"]
ALLOWED_METHODS=["GET", "POST", "PUT", "DELETE"]
ALLOWED_HEADERS=["*"]

RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60

MAX_REQUEST_SIZE=1048576
MAX_FIELD_SIZE=65536
MAX_TEXT_LENGTH=10000
MAX_COMMENT_LENGTH=2000

REQUEST_TIMEOUT=30
KEEP_ALIVE_TIMEOUT=5

NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
NOTION_REDIRECT_URI=http://localhost:8000/api/auth/notion/callback

DATABASE_URL=sqlite:///./notes.db
"""
    
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write(env_template)
        print("✅ Created .env file with default settings")
    else:
        print("⚠️  .env file already exists, skipping creation")


def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True, text=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(f"Error output: {e.stderr}")
        return False


def test_import():
    """Test if the app can be imported"""
    try:
        from app.main import app
        print("✅ App imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def run_tests():
    """Run basic API tests"""
    print("🧪 Running basic tests...")
    
    # Test configuration
    try:
        from app.config import settings
        print(f"✅ Configuration loaded (Environment: {settings.environment})")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    # Test schemas
    try:
        from app.schemas.note import NoteCreate
        test_note = NoteCreate(
            text="Test note",
            url="https://example.com",
            title="Test Page"
        )
        print("✅ Schemas validation working")
    except Exception as e:
        print(f"❌ Schema error: {e}")
        return False
    
    return True


def main():
    """Main setup function"""
    print("🚀 Smart Notes API Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Setup steps
    steps = [
        # ("Creating environment file", create_env_file),
        ("Installing dependencies", install_dependencies), 
        ("Testing imports", test_import),
        ("Running tests", run_tests),
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            sys.exit(1)
    
    print("\n🎉 Setup completed successfully!")
    print("\n🚀 To start the server:")
    print("   python run.py")
    print("\n📚 API docs will be available at:")
    print("   http://127.0.0.1:8000/docs")
    print("\n🧪 Test the API:")
    print("   curl http://127.0.0.1:8000/health")


if __name__ == "__main__":
    main()
