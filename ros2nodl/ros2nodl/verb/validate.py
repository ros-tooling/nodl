"""``ros2 nodl validate <files>`` — validate NoDL documents against the schema."""

import sys
from pathlib import Path

import yaml

from nodl_schema import validate

from ros2nodl.verb import VerbExtension


class ValidateVerb(VerbExtension):
    """Validate NoDL document(s) against the NoDL schema."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            "files",
            nargs="+",
            type=Path,
            help="NoDL YAML files to validate.",
        )

    def main(self, *, args):
        rc = 0
        for path in args.files:
            with open(path, "r") as f:
                document = yaml.safe_load(f)
            errors = validate(document)
            if errors:
                rc = 1
                print(f"{path}: INVALID", file=sys.stderr)
                for err in errors:
                    print(f"  {err}", file=sys.stderr)
            else:
                print(f"{path}: ok")
        return rc
