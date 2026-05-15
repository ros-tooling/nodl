import sys

from ros2nodl.verb import VerbExtension


class ValidateVerb(VerbExtension):
    """Validate a NoDL file against the NoDL JSON schema."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            'file',
            nargs='?',
            help='NoDL file to validate (YAML or JSON). Reads from stdin if omitted.',
        )
        parser.add_argument(
            '--format',
            choices=['yaml', 'json'],
            default=None,
            help='Force input format (default: auto-detect).',
        )

    def main(self, *, args):
        from jsonschema import ValidationError
        from nodl.schema import load_nodl

        try:
            source = sys.stdin if args.file is None else open(args.file)
        except OSError as e:
            print(f'Error: {e}', file=sys.stderr)
            return 1

        try:
            load_nodl(source, format=args.format)
        except ValidationError as e:
            print(f'Validation error: {e.message}', file=sys.stderr)
            print(f'  at: {" -> ".join(str(p) for p in e.absolute_path)}', file=sys.stderr)
            return 1
        except Exception as e:
            print(f'Error: {e}', file=sys.stderr)
            return 1
        finally:
            if args.file is not None:
                source.close()

        print('Valid NoDL document.')
        return 0
