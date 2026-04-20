from __future__ import annotations

import click

from vera import __version__
from vera.cli.cmd_adapters import adapters_group
from vera.cli.cmd_add import add_cmd
from vera.cli.cmd_cd import cd_cmd
from vera.cli.cmd_discover import discover_cmd
from vera.cli.cmd_grade import grade_cmd
from vera.cli.cmd_info import info_cmd
from vera.cli.cmd_list import list_cmd
from vera.cli.cmd_new import new_cmd
from vera.cli.cmd_shell import shell_cmd
from vera.cli.cmd_start import start_cmd
from vera.cli.cmd_status import status_cmd
from vera.cli.cmd_submit import submit_cmd
from vera.cli.cmd_test import test_cmd
from vera.cli.cmd_update import update_cmd


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="vera")
def main() -> None:
    """vera — a format for human-AI engineering runs."""


main.add_command(list_cmd, name="list")
main.add_command(info_cmd, name="info")
main.add_command(add_cmd, name="add")
main.add_command(start_cmd, name="start")
main.add_command(status_cmd, name="status")
main.add_command(grade_cmd, name="grade")
main.add_command(submit_cmd, name="submit")
main.add_command(new_cmd, name="new")
main.add_command(test_cmd, name="test")
main.add_command(cd_cmd, name="cd")
main.add_command(shell_cmd, name="shell")
main.add_command(discover_cmd, name="discover")
main.add_command(update_cmd, name="update")
main.add_command(adapters_group, name="adapters")


if __name__ == "__main__":
    main()
