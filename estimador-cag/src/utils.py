def get_absolute_path():
    from pathlib import Path

    # 1. Detect the directory in a hybrid and foolproof way
    if "__file__" in globals():
        # Code running as a standard .py script (Local, Docker, Cloud)
        BASE_DIR = Path(__file__).resolve().parent
    elif "__vsc_ipynb_file__" in globals():
        # Code running inside a Jupyter Notebook within VS Code
        BASE_DIR = Path(__vsc_ipynb_file__).resolve().parent
    else:
        # Generic Jupyter Notebook or other interactive environments
        BASE_DIR = Path.cwd().resolve()
    return BASE_DIR