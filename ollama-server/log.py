import logging
import sys

# ANSI color codes
BLACK = '\033[0;30m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
MAGENTA = '\033[0;35m'
CYAN = '\033[0;36m'
WHITE = '\033[0;37m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log messages based on level"""

    COLORS = {
        logging.DEBUG: BLUE,
        logging.INFO: NC,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: MAGENTA + BOLD,
    }

    def format(self, record):
        # Get the original message
        log_message = super().format(record)
        # Apply color based on log level
        return f"{self.COLORS.get(record.levelno, NC)}{log_message}{NC}"

def setup_colored_logging(name=None, level=logging.INFO):
    """
    Set up colored logging for the specified logger.
    
    Args:
        name: Logger name (None for root logger)
        level: Logging level
        
    Returns:
        Logger instance
    """
    # Create a console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Create formatter with colors
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add formatter to handler
    console_handler.setFormatter(formatter)

    # Get the logger and add handler
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add our handler
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    # unless this is the root logger
    if name is not None:
        logger.propagate = False

    return logger

# Convenience functions for direct colored printing
def print_colored(text, color):
    """Print colored text to terminal"""
    print(f"{color}{text}{NC}")

def print_info(text):
    """Print info message in green"""
    print_colored(text, NC)

def print_warning(text):
    """Print warning message in yellow"""
    print_colored(text, YELLOW)

def print_error(text):
    """Print error message in red"""
    print_colored(text, RED)

def print_debug(text):
    """Print debug message in blue"""
    print_colored(text, BLUE)
