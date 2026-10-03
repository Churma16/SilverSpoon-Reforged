import os
from pathlib import Path


def pytest_configure(config):
    """Automatically loads .env file variables into os.environ for local test runs."""
    project_root_directory = Path(__file__).resolve().parent.parent
    environment_file_path = project_root_directory / ".env"

    if environment_file_path.exists():
        with open(environment_file_path, "r", encoding="utf-8") as file_stream:
            for line in file_stream:
                cleaned_line = line.strip()
                if cleaned_line and not cleaned_line.startswith("#") and "=" in cleaned_line:
                    variable_key, variable_value = cleaned_line.split("=", 1)
                    variable_key = variable_key.strip()
                    variable_value = variable_value.strip().strip("'\"")
                    if variable_key and variable_key not in os.environ:
                        os.environ[variable_key] = variable_value
