import json
import re
import traceback
from pathlib import Path

import click
import toml
import yaml
from rich.console import Console

from .config_reader import (
    ConfigError,
    ConfigType,
    JSONConfig,
    TOMLConfig,
    YAMLConfig,
    detect_config_type_by_extension,
)
from .exceptions import ConfigError as ConfigDoctorError

console = Console()


@click.group()
def cli():
    """Software for quickly creating and building C/C++ projects."""


@cli.command()
@click.argument("target", nargs=-1, required=True)
def check(target: list):
    """Check and lint target dir or file."""


def _print_troubleshooting_tips(extension: str):
    """Print format-specific troubleshooting tips."""
    console.print("\n💡 TROUBLESHOOTING TIPS" + "\n" + "=" * 30, err=True)

    tips = {
        ".json": [
            "• Check for missing commas between object properties",
            "• Ensure all strings are properly quoted with double quotes",
            "• Verify that brackets {} and [] are properly balanced",
            "• Remove trailing commas in arrays and objects",
            "• Validate your JSON online: https://jsonlint.com/",
        ],
        ".toml": [
            "• Verify table headers are in format [table_name]",
            "• Check that keys and values are properly separated by =",
            "• Ensure strings are properly quoted when needed",
            "• Verify array syntax uses brackets []",
            "• TOML spec: https://toml.io/en/",
        ],
        ".yaml": [
            "• Check consistent indentation (spaces recommended, not tabs)",
            "• Verify colons after keys have proper spacing",
            "• Ensure proper quoting for special characters",
            "• Check that multiline strings use | or > correctly",
            "• YAML validator: https://www.yamllint.com/",
        ],
        ".yml": [
            "• Check consistent indentation (spaces recommended, not tabs)",
            "• Verify colons after keys have proper spacing",
            "• Ensure proper quoting for special characters",
            "• Check that multiline strings use | or > correctly",
            "• YAML validator: https://www.yamllint.com/",
        ],
    }

    file_tips = tips.get(
        extension.lower(),
        [
            "• Check the file syntax matches the expected format",
            "• Verify there are no encoding issues",
            "• Ensure the file is not corrupted",
            "• Try validating with a format-specific validator",
        ],
    )

    for tip in file_tips:
        console.print(f"  {tip}", err=True)

    console.print(
        "\n📚 Documentation: https://github.com/your-username/your-project/docs/configuration",
        err=True,
    )


def _extract_line_number_from_error(error_message: str, lines: list) -> int | None:
    """Extract line number from common parser error messages."""
    error_lower = error_message.lower()

    # Common patterns in error messages
    patterns = [
        r"line (\d+)",
        r"at line (\d+)",
        r"line (\d+) column",
        r"line (\d+)",
        r"line (\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            try:
                line_num = int(match.group(1)) - 1
                if 0 <= line_num < len(lines):
                    return line_num
            except ValueError:
                continue

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped.endswith(":") or (
            "=" in line
            and not line_stripped.endswith('"')
            and not line_stripped.endswith("'")
        ):
            return i

    return None


def _print_detailed_error_info(config_file: Path, error_message: str):
    """Print detailed error information with line numbers and context."""
    console.print("\n" + "🔍 DETAILED ERROR ANALYSIS" + "\n" + "=" * 40, err=True)

    console.print(f"📄 File: {config_file}", err=True)
    console.print(f"📏 Size: {config_file.stat().st_size} bytes", err=True)

    try:
        content = config_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        console.print(f"📊 Lines: {len(lines)}", err=True)
        console.print(f"💬 Error: {error_message}", err=True)

        line_number = _extract_line_number_from_error(error_message, lines)

        if line_number is not None and 0 <= line_number < len(lines):
            console.print(f"\n📍 Problem around line {line_number + 1}:", err=True)
            console.print("┌" + "─" * 40, err=True)

            start = max(0, line_number - 2)
            end = min(len(lines), line_number + 3)

            for i in range(start, end):
                marker = ">>>" if i == line_number else "   "
                line_num = i + 1
                try:
                    line_content = lines[i].replace("\t", "    ")
                    console.print(f"{marker} {line_num:3d} │ {line_content}", err=True)
                except Exception:
                    console.print(
                        f"{marker} {line_num:3d} │ [cannot display line]", err=True
                    )

            console.print("└" + "─" * 40, err=True)

    except Exception as read_error:
        console.print(
            f"⚠️  Could not read file for detailed analysis: {read_error}", err=True
        )

    _print_troubleshooting_tips(config_file.suffix)


@cli.command()
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--fileformat",
    type=click.Choice(["auto", "toml", "yaml", "json"]),
    default="auto",
    help="Config file format (default: auto-detect)",
)
def view(config_file: Path, fileformat: str):  # noqa: C901
    """View configuration file contents with detailed error reporting."""
    try:
        if fileformat == "auto":
            try:
                config_type = detect_config_type_by_extension(config_file.suffix)
            except ConfigError as e:
                console.print(f"❌ Error detecting config type: {e}", err=True)
                console.print("\n💡 Supported formats: .toml, .yaml, .yml, .json")
                return 1
        else:
            format_map = {
                "toml": ConfigType.TOML,
                "yaml": ConfigType.YAML,
                "json": ConfigType.JSON,
            }
            config_type = format_map[fileformat]

        if config_type == ConfigType.JSON:
            config_reader = JSONConfig(config_file)
        elif config_type == ConfigType.TOML:
            config_reader = TOMLConfig(config_file)
        elif config_type == ConfigType.YAML:
            config_reader = YAMLConfig(config_file)
        else:
            console.print(f"❌ Unsupported config type: {config_type}", err=True)
            return 1

        config_data = config_reader.get_loaded_config()

        console.print(f"📁 Config file: {config_file}")
        console.print(f"📝 Format: {config_type.name}")
        console.print("=" * 50)

        if config_type == ConfigType.JSON:
            print(json.dumps(config_data, indent=2, ensure_ascii=False))
        elif config_type == ConfigType.YAML:
            print(yaml.dump(config_data, default_flow_style=False, allow_unicode=True))
        elif config_type == ConfigType.TOML:
            print(toml.dumps(config_data))

    except ConfigDoctorError as e:
        console.print(f"❌ Configuration Error: {e}", err=True)
        _print_detailed_error_info(config_file, str(e))
        return 1
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", err=True)
        console.print("\n🔧 Debug information:")
        console.print(traceback.format_exc())
        return 1

    return 0


def main():
    """Main function."""
    cli()
