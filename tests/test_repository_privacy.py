from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATH_PARTS = {
    "ledger",
    "vault",
    "travel_spend_charts.py",
}
FORBIDDEN_TEXT_MARKERS = (
    "curated travel-spending figures",
    "Notion travel ledger",
    "Ledger/data/clean",
)


class RepositoryPrivacyTests(unittest.TestCase):
    def test_repository_contains_no_known_private_source_material(self) -> None:
        path_offenders: list[str] = []
        text_offenders: list[str] = []

        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        relative_paths = sorted(
            Path(value.decode("utf-8"))
            for value in result.stdout.split(b"\0")
            if value
        )
        for relative in relative_paths:
            path = REPO_ROOT / relative
            if path.resolve() == Path(__file__).resolve():
                continue
            lowered_parts = {part.lower() for part in relative.parts}
            if lowered_parts.intersection(FORBIDDEN_PATH_PARTS):
                path_offenders.append(relative.as_posix())
                continue
            if not path.is_file():
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="replace")
            for marker in FORBIDDEN_TEXT_MARKERS:
                if marker.lower() in text.lower():
                    text_offenders.append(f"{relative}: {marker}")

        self.assertEqual(path_offenders, [])
        self.assertEqual(text_offenders, [])


if __name__ == "__main__":
    unittest.main()
