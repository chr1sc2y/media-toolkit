import ast
import importlib
import unittest
from pathlib import Path

from media_toolkit.command_registry import (
    Command,
    command_registry_dict,
    list_commands,
    resolve_command,
    validate_command_registry,
)


class CommandRegistryTest(unittest.TestCase):
    def test_registry_exposes_agent_relevant_command_metadata(self):
        registry = command_registry_dict(visible_only=True)
        commands = {command["canonical"]: command for command in registry["commands"]}

        self.assertEqual(registry["version"], 1)
        self.assertIn("finalize", commands)
        self.assertTrue(commands["finalize"]["requires_destination"])
        self.assertIn("copy", commands["finalize"]["side_effects"])
        self.assertTrue(commands["organize"]["supports_dry_run"])
        self.assertIn("move", commands["organize"]["side_effects"])
        self.assertTrue(commands["fill-locations"]["supports_dry_run"])
        self.assertIn(
            "optional-photos-update",
            commands["fill-locations"]["side_effects"],
        )

    def test_commands_entrypoint_is_package_first(self):
        command = resolve_command("commands")

        self.assertEqual(command.module_name, "media_toolkit.commands.commands")

    def test_registry_validation_rejects_duplicate_aliases(self):
        commands = [
            Command("one", ("shared",), "one.py", "one", "media_toolkit.commands.one"),
            Command("two", ("shared",), "two.py", "two", "media_toolkit.commands.two"),
        ]

        with self.assertRaisesRegex(ValueError, "shared"):
            validate_command_registry(commands)

    def test_registry_validation_accepts_current_commands(self):
        validate_command_registry(list_commands())

    def test_visible_commands_have_package_modules(self):
        missing = [
            command.canonical
            for command in list_commands(visible_only=True)
            if not command.module_name
        ]

        self.assertEqual(missing, [])

    def test_visible_command_modules_are_importable(self):
        failures: list[str] = []
        for command in list_commands(visible_only=True):
            assert command.module_name is not None
            try:
                importlib.import_module(command.module_name)
            except Exception as exc:
                failures.append(f"{command.canonical}: {exc}")

        self.assertEqual(failures, [])

    def test_visible_command_scripts_exist(self):
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        missing = [
            command.script_name
            for command in list_commands(visible_only=True)
            if not (scripts_dir / command.script_name).exists()
        ]

        self.assertEqual(missing, [])

    def test_script_entrypoints_are_thin_wrappers(self):
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        offenders: list[str] = []
        for script in sorted(scripts_dir.glob("*.py")):
            tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
            definitions = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            if definitions:
                offenders.append(f"{script.name}: {', '.join(definitions)}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
