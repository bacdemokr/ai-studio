#!/usr/bin/env python3
"""Public entry point for Spark setup, model removal and application updates."""
import argparse
import json
import platform
import shutil
import subprocess
import sys

import ops_common as c
import ops_deploy as app
import ops_llm as llm
import ops_runtime as runtime


def main():
    parser = argparse.ArgumentParser(description='Manage the BaC app independently from its shared LLM.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('doctor', 'status', 'update', 'rollback'):
        commands.add_parser(name)
    application = commands.add_parser('app').add_subparsers(dest='action', required=True)
    start = application.add_parser('start')
    start.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'])
    start.add_argument('--port', type=int)
    for name in ('stop', 'logs'):
        application.add_parser(name)
    model = commands.add_parser('llm').add_subparsers(dest='action', required=True)
    for name in ('plan', 'setup', 'start', 'remove'):
        command = model.add_parser(name)
        command.add_argument('model', choices=['qwen', 'gemma'])
        if name == 'remove':
            command.add_argument('--yes', action='store_true')
    for name in ('stop', 'check', 'logs', 'remove-runtime'):
        command = model.add_parser(name)
        if name == 'remove-runtime':
            command.add_argument('--yes', action='store_true')
    agent = commands.add_parser('runtime').add_subparsers(dest='action', required=True)
    for name in ('setup', 'start', 'stop', 'check', 'logs'):
        agent.add_parser(name)
    shell = commands.add_parser('openshell').add_subparsers(dest='action', required=True)
    for name in ('enable', 'check'):
        shell.add_parser(name)
    commands.add_parser('telegram').add_subparsers(dest='action', required=True).add_parser('configure')
    commands.add_parser('search').add_subparsers(dest='action', required=True).add_parser('configure')
    args = parser.parse_args()
    if args.command in ('runtime', 'openshell', 'telegram', 'search'):
        if args.command == 'runtime' and args.action == 'check':
            runtime.check()
        elif args.command == 'runtime' and args.action == 'logs':
            c.run(['journalctl', '--user', '-u', 'bac-openclaw', '-n', '100', '--no-pager'])
        else:
            with c.locked():
                if args.command == 'openshell':
                    runtime.openshell(args.action)
                elif args.command == 'search':
                    runtime.configure_search()
                elif args.command == 'telegram':
                    runtime.configure_telegram()
                elif args.action == 'setup':
                    runtime.setup()
                elif args.action == 'start':
                    runtime.start()
                elif args.action == 'stop':
                    c.service('bac-openclaw', 'stop')
        return
    if args.command == 'doctor':
        print('Host:', platform.system(), platform.machine())
        for tool in ('git', 'python3', 'nvidia-smi', 'ffmpeg', 'uv', 'systemctl'):
            print(tool + ':', shutil.which(tool) or 'not found')
        print('systemd user session:', 'available' if c.systemd_available() else 'unavailable')
        print('Data directory:', c.home())
        print('uv can be bootstrapped locally during setup; OS packages/drivers are not installed by ./bac.')
        return
    if args.command == 'status':
        app.status()
        return
    if args.command == 'llm' and args.action == 'plan':
        command, spec = llm.command(args.model)
        print(json.dumps({'python': llm.profiles()['python'], 'packages': llm.profiles()['packages'],
                          'model': spec['id'], 'revision': spec['revision'],
                          'environment': llm.profiles()['environment'], 'command': command}, indent=2))
        return
    if args.command == 'llm' and args.action == 'check':
        llm.check()
        return
    if args.command in ('app', 'llm') and args.action == 'logs':
        c.require_systemd()
        c.run(['journalctl', '--user', '-u', 'bac-demo' if args.command == 'app' else 'bac-llm', '-n', '100', '--no-pager'])
        return
    with c.locked():
        if args.command == 'update':
            app.update()
        elif args.command == 'rollback':
            app.rollback()
        elif args.command == 'app':
            if args.action == 'start':
                if args.port is not None and not 1024 <= args.port <= 65535:
                    raise RuntimeError('Use an application port between 1024 and 65535.')
                app.start(args.host, args.port)
            else:
                c.service('bac-demo', 'stop')
        elif args.action == 'setup':
            llm.setup(args.model)
        elif args.action == 'start':
            llm.start(args.model)
        elif args.action == 'remove':
            llm.remove(args.model, args.yes)
        elif args.action == 'remove-runtime':
            llm.remove_runtime(args.yes)
        elif args.action == 'stop':
            c.service('bac-llm', 'stop')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('BaC:', error, file=sys.stderr)
        sys.exit(1)
