#!/usr/bin/env python3
"""Interactive setup script for the Python package template."""

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_step(text: str) -> None:
    print(f"  -> {text}")


def print_success(text: str) -> None:
    print(f"  [OK] {text}")


def print_error(text: str) -> None:
    print(f"  [ERROR] {text}", file=sys.stderr)


def ask(prompt: str, default: str = "") -> str:
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    while True:
        result = input(f"{prompt}: ").strip()
        if result:
            return result
        print("  This field is required.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    result = input(f"{prompt} [{default_str}]: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def validate_package_name(name: str) -> bool:
    pattern = r"^[a-zA-Z][a-zA-Z0-9]*(-[a-zA-Z0-9]+)*$"
    return bool(re.match(pattern, name))


def to_underscore(name: str) -> str:
    return name.replace("-", "_")


def replace_in_file(filepath: Path, replacements: dict[str, str]) -> None:
    content = filepath.read_text()
    for old, new in replacements.items():
        content = content.replace(old, new)
    filepath.write_text(content)


def run_command(args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def main() -> int:
    print_header("Python package template setup")

    print("This script will configure the template for your project.\n")

    while True:
        package_name = ask("Package name (e.g., my-awesome-lib)")
        if validate_package_name(package_name):
            break
        print("  Invalid name. Use letters, numbers, and hyphens (e.g., my-package).")

    package_underscore = to_underscore(package_name)
    package_title = package_name.replace("-", " ").title()
    description = ask("Package description")
    author_name = ask("Author name")
    author_email = ask("Author email")
    github_username = ask("GitHub username or organization")
    include_docs = ask_yes_no("Include Starlight documentation site?", default=True)

    current_year = str(datetime.now().year)

    print_header("Configuration summary")
    print(f"  Package name:    {package_name}")
    print(f"  Python import:   {package_underscore}")
    print(f"  Description:     {description}")
    print(f"  Author:          {author_name} <{author_email}>")
    print(f"  GitHub:          {github_username}/{package_name}")
    print(f"  Documentation:   {'Yes (Starlight)' if include_docs else 'No'}")
    print()

    confirm = input("Proceed with setup? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("\nSetup cancelled.")
        return 1

    print_header("Configuring project")

    src_old = SCRIPT_DIR / "src" / "package_name"
    src_new = SCRIPT_DIR / "src" / package_underscore
    if src_old.exists():
        print_step(f"Renaming src/package_name/ to src/{package_underscore}/")
        shutil.move(str(src_old), str(src_new))
        print_success("Package directory renamed")

    replacements = {
        "opencitations/python-package-template": f"{github_username}/{package_name}",
        "python-package-template": package_name,
        "package-name": package_name,
        "package_name": package_underscore,
        "Package Name": package_title,
        "Python Package Template": package_title,
        "Package description": description,
        "A template for creating Python packages with UV, pytest, and Starlight documentation": description,
        "Author Name": author_name,
        "author@example.com": author_email,
        "opencitations": github_username,
        "[year]": current_year,
        "[author]": author_name,
    }

    files_to_update = [
        SCRIPT_DIR / "pyproject.toml",
        SCRIPT_DIR / "LICENSE.md",
        SCRIPT_DIR / "src" / package_underscore / "__init__.py",
        SCRIPT_DIR / "tests" / "test_example.py",
        SCRIPT_DIR / ".github" / "workflows" / "tests.yml",
    ]

    for filepath in files_to_update:
        if filepath.exists():
            print_step(f"Updating {filepath.relative_to(SCRIPT_DIR)}")
            replace_in_file(filepath, replacements)
            print_success(f"{filepath.name} updated")

    readme_template = SCRIPT_DIR / "README_TEMPLATE.md"
    readme_path = SCRIPT_DIR / "README.md"
    if readme_template.exists():
        print_step("Generating README.md from template...")
        content = readme_template.read_text()
        for old, new in replacements.items():
            content = content.replace(old, new)
        readme_path.write_text(content)
        print_success("README.md generated")

    docs_dir = SCRIPT_DIR / "docs"
    if include_docs:
        if docs_dir.exists():
            print_step("Updating documentation files...")
            docs_files = [
                docs_dir / "astro.config.mjs",
                docs_dir / "src" / "content" / "docs" / "index.mdx",
                docs_dir / "src" / "content" / "docs" / "getting_started.md",
            ]
            for filepath in docs_files:
                if filepath.exists():
                    replace_in_file(filepath, replacements)
            print_success("Documentation files updated")
    else:
        if docs_dir.exists():
            print_step("Removing documentation directory...")
            shutil.rmtree(docs_dir)
            print_success("docs/ removed")

        deploy_docs_workflow = SCRIPT_DIR / ".github" / "workflows" / "deploy-docs.yml"
        if deploy_docs_workflow.exists():
            print_step("Removing documentation workflow...")
            deploy_docs_workflow.unlink()
            print_success("deploy-docs.yml removed")

        if readme_path.exists():
            print_step("Updating README.md (removing docs section)...")
            content = readme_path.read_text()
            content = re.sub(
                r"\n## Documentation\n.*?(?=\n## |\Z)",
                "",
                content,
                flags=re.DOTALL,
            )
            content = re.sub(
                r"\n### Building documentation locally\n.*?(?=\n## |\n### |\Z)",
                "",
                content,
                flags=re.DOTALL,
            )
            readme_path.write_text(content)
            print_success("README.md updated")

    print_step("Checking for UV...")
    uv_available = shutil.which("uv") is not None

    if uv_available:
        print_step("Running uv sync --all-extras --dev")
        success, output = run_command(
            ["uv", "sync", "--all-extras", "--dev"],
            cwd=SCRIPT_DIR,
        )
        if success:
            print_success("Dependencies installed")
        else:
            print_error("uv sync failed. Run it manually after setup.")
            print(output)
    else:
        print("  UV not found. Run 'uv sync --all-extras --dev' manually.")

    print_step("Removing setup files")
    setup_files = [
        SCRIPT_DIR / "setup.py",
        SCRIPT_DIR / "README_TEMPLATE.md",
    ]
    for filepath in setup_files:
        if filepath.exists():
            filepath.unlink()

    images_dir = SCRIPT_DIR / ".github" / "images"
    if images_dir.exists():
        shutil.rmtree(images_dir)

    print_success("Setup files removed")

    print_header("Setup complete")
    print("Your project is ready. Next steps:\n")
    print("1. Configure GitHub repository:")
    print("   - Create PyPI token: https://pypi.org/manage/account/token/")
    print(f"   - Add as secret: https://github.com/{github_username}/{package_name}/settings/secrets/actions/new")
    print("     Name: PYPI_TOKEN")
    if include_docs:
        print(f"   - Enable GitHub Pages: https://github.com/{github_username}/{package_name}/settings/pages")
        print("     Source: GitHub Actions")
    print()
    print("2. Commit and push:")
    print("   git add .")
    print('   git commit -m "feat: initial project setup"')
    print("   git push")
    if include_docs:
        print()
        print("   Warning: if GitHub Pages is not configured with 'GitHub Actions'")
        print("   as source, the documentation deployment will fail.")
    print()
    print("3. Start developing:")
    print(f"   - Edit src/{package_underscore}/__init__.py")
    print("   - Add tests in tests/")
    if include_docs:
        print("   - Update documentation in docs/src/content/docs/")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
