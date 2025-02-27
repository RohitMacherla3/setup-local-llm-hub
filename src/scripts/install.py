"""Script to install Ollama on the system"""
import subprocess
import os
import sys
import platform
import shutil
import requests

# ANSI colors for output
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def print_colored(text, color):
    """Print colored text to terminal"""
    print(f"{color}{text}{NC}")

def check_ollama_installed():
    """Check if Ollama is installed on the system"""
    try:
        subprocess.run(["ollama", "--version"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        return False

def install_ollama():
    """Install Ollama based on the operating system"""
    system = platform.system().lower()
    print(f"Detected operating system: {system}")

    print_colored("Installing Ollama...", YELLOW)

    if system == "linux":
        # Linux installation
        try:
            # Check if we can use apt (Debian/Ubuntu)
            if os.path.exists("/usr/bin/apt"):
                print("Detected Debian/Ubuntu system, using apt...")
                subprocess.run(
                    "curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True,
                    check=True
                )
            # Check if we can use yum/dnf (Fedora/RHEL/CentOS)
            elif os.path.exists("/usr/bin/dnf") or os.path.exists("/usr/bin/yum"):
                print("Detected Fedora/RHEL/CentOS system, using yum/dnf...")
                subprocess.run(
                    "curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True,
                    check=True
                )
            else:
                print("Using generic Linux installation method...")
                subprocess.run(
                    "curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True,
                    check=True
                )
            print_colored("Ollama installed successfully.", GREEN)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Ollama: {e}")
            print("Please install manually from https://ollama.com")
            return False

    elif system == "darwin":
        # macOS installation
        try:
            # Check if Homebrew is installed
            if shutil.which("brew"):
                print("Detected Homebrew, using brew install...")
                subprocess.run(
                    "brew install ollama",
                    shell=True,
                    check=True
                )
            else:
                print("Using direct installation method...")
                subprocess.run(
                    "curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True,
                    check=True
                )
            print_colored("Ollama installed successfully.", GREEN)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Ollama: {e}")
            print("Please install manually from https://ollama.com")
            return False

    elif system == "windows":
        try:
            # Download the Windows installer
            print("Downloading Ollama Windows installer...")
            installer_url = "https://ollama.com/download/ollama-windows-amd64.msi"
            installer_path = os.path.join(os.environ["TEMP"], "ollama-installer.msi")

            # Use requests to download if available
            try:
                print("Downloading with requests...")
                response = requests.get(installer_url)
                with open(installer_path, "wb") as f:
                    f.write(response.content)
            except (ImportError, Exception) as e:
                print(f"Failed to download with requests: {e}")
                print("Falling back to PowerShell...")
                # Fallback to PowerShell
                ps_command = f'[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri "{installer_url}" -OutFile "{installer_path}"'
                subprocess.run(["powershell", "-Command", ps_command], check=True)

            # Run the installer
            print_colored("Starting installer. Please follow the on-screen instructions...", YELLOW)
            subprocess.run(["msiexec", "/i", installer_path], check=True)

            print_colored("Ollama installation completed.", GREEN)
            print("Note: You may need to restart your terminal or computer for changes to take effect.")
            return True
        except Exception as e:
            print(f"Failed to install Ollama on Windows: {e}")
            print("Please install manually from https://ollama.com")
            return False

    else:
        print(f"Unsupported operating system: {system}")
        return False

def main():
    """Main entry point"""
    # Check if Ollama is installed
    if not check_ollama_installed():
        print_colored("Ollama is not installed.", YELLOW)

        if input("Do you want to install Ollama? [y/N]: ").lower() == 'y':
            if not install_ollama():
                return 1
        else:
            print("Ollama installation skipped. Some features may not work without Ollama.")
    else:
        print_colored("Ollama is already installed.", GREEN)

if __name__ == "__main__":
    sys.exit(main())
