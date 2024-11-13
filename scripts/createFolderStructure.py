import os

def create_project_structure(base_path, project_name):
    # Define directory structure
    dirs = [
        f"{base_path}/{project_name}/src/{project_name}/utils",
        f"{base_path}/{project_name}/src/{project_name}/components",
        f"{base_path}/{project_name}/src/tests",
        f"{base_path}/{project_name}/docs",
        f"{base_path}/{project_name}/data/raw",
        f"{base_path}/{project_name}/data/processed",
        f"{base_path}/{project_name}/scripts",
        f"{base_path}/{project_name}/notebooks"
    ]

    # Define files with initial content if desired
    files = {
        f"{base_path}/{project_name}/src/{project_name}/__init__.py": "",
        f"{base_path}/{project_name}/src/{project_name}/main_module.py": "# Main module entry point\n",
        f"{base_path}/{project_name}/src/{project_name}/config.py": "# Configuration settings\n",
        f"{base_path}/{project_name}/src/{project_name}/utils/__init__.py": "",
        f"{base_path}/{project_name}/src/{project_name}/components/__init__.py": "",
        f"{base_path}/{project_name}/src/tests/__init__.py": "",
        f"{base_path}/{project_name}/src/tests/test_main_module.py": "# Test cases for main module\n",
        f"{base_path}/{project_name}/docs/installation.md": "# Installation Guide\n",
        f"{base_path}/{project_name}/docs/usage.md": "# Usage Instructions\n",
        f"{base_path}/{project_name}/docs/architecture.md": "# Architectural Overview\n",
        f"{base_path}/{project_name}/requirements.txt": "# Project dependencies\n",
        f"{base_path}/{project_name}/setup.py": "# Setup script for packaging\n",
        f"{base_path}/{project_name}/.env": "# Environment variables\n",
        f"{base_path}/{project_name}/.gitignore": "# Files to ignore in Git\n__pycache__/\n*.pyc\n.env\n",
        f"{base_path}/{project_name}/README.md": f"# {project_name.capitalize()} Project\n\nProject overview and instructions.\n"
    }

    # Create directories
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

    # Create files with initial content
    for file_path, content in files.items():
        with open(file_path, 'w') as file:
            file.write(content)
        print(f"Created file: {file_path}")

    print("Project structure created successfully!")

# Usage
project_name = "podcastGenerator"  # Replace with your project name
base_path = "."  # Replace with your desired base path, e.g., "/path/to/projects"
create_project_structure(base_path, project_name)