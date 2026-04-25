"""Remote command implementation"""

from ..base import BaseCommand


class RemoteCommand(BaseCommand):
    """Manage remote machines for file transfers"""

    name = "remote"
    description = "Manage remote machines for downloads"
    category = "Configuration"

    def setup_parser(self, subparsers):
        """Setup argument parser for remote command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for remote subcommands
        remote_subparsers = parser.add_subparsers(
            dest='remote_subcommand',
            help='Remote subcommands'
        )

        # remote add subcommand
        add_parser = remote_subparsers.add_parser(
            'add',
            add_help=False,
            help='Add a new remote machine'
        )
        add_parser.add_argument('name', nargs='?', help='Remote name')
        add_parser.add_argument('--user', type=str, metavar='USER', help='SSH username')
        add_parser.add_argument('--ip', type=str, metavar='IP', help='IP address or hostname')
        add_parser.add_argument('--password', type=str, metavar='PASS', help='SSH password')
        add_parser.add_argument('--port', type=int, metavar='PORT', default=22, help='SSH port (default: 22)')
        add_parser.add_argument('--path', type=str, metavar='PATH', help='Base directory on remote')
        add_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # remote modify subcommand
        modify_parser = remote_subparsers.add_parser(
            'modify',
            add_help=False,
            help='Modify a remote machine'
        )
        modify_parser.add_argument('name', nargs='?', help='Remote name')
        modify_parser.add_argument('--user', type=str, metavar='USER', help='SSH username')
        modify_parser.add_argument('--ip', type=str, metavar='IP', help='IP address or hostname')
        modify_parser.add_argument('--password', type=str, metavar='PASS', help='SSH password')
        modify_parser.add_argument('--port', type=int, metavar='PORT', help='SSH port')
        modify_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # remote delete subcommand
        delete_parser = remote_subparsers.add_parser(
            'delete',
            add_help=False,
            help='Delete a remote machine'
        )
        delete_parser.add_argument('name', nargs='?', help='Remote name')
        delete_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # remote list subcommand
        list_parser = remote_subparsers.add_parser(
            'list',
            add_help=False,
            help='List all remote machines'
        )
        list_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # remote set-path subcommand
        setpath_parser = remote_subparsers.add_parser(
            'set-path',
            add_help=False,
            help='Set base path for a remote'
        )
        setpath_parser.add_argument('name', nargs='?', help='Remote name')
        setpath_parser.add_argument('--path', type=str, metavar='PATH', help='Base directory on remote')
        setpath_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # General help for remote command
        parser.add_argument('-h', '--help', action='store_true', help='Show help')

        return parser

    def execute(self, args):
        """Execute remote command"""
        if hasattr(args, 'help') and args.help and not hasattr(args, 'remote_subcommand'):
            self.show_help()
            return

        # Get subcommand
        subcommand = getattr(args, 'remote_subcommand', None)

        if not subcommand:
            self.show_help()
            return

        # Route to subcommand handler
        from .remote_impl import command as remote_cmd
        remote_cmd.execute_remote(args)

    def show_help(self):
        """Show help message"""
        from .remote_impl import command as remote_cmd
        remote_cmd.show_remote_help()


# Export command class
remote_command = RemoteCommand

