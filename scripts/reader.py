"""Reader entry point: CPU Laya, optional explicitly selected reasoning API."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

from laya_pokemon.core import parse_rom_header, utc_now, write_json
from laya_pokemon.local_planner import (
    PlannerError, StrataPlanner, allowed_stages, strict_object,
)
from laya_pokemon.policy import PINNED_REVISION

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.local/reader.json'
RED_SHA = '5ca7ba01642a3b27b0cc0b5349b52792795b62d3ed977e98a09390659af96b7b'


def recommendation(total_gib, available_gib):
    # Conservative CPU/RAM starting points, not guarantees or GPU benchmarks.
    if total_gib >= 24 and available_gib >= 16:
        return 'qwen3:8b'
    if total_gib >= 15 and available_gib >= 10:
        return 'qwen3:4b'
    return None


def hardware():
    import psutil
    memory = psutil.virtual_memory()
    total, available = memory.total / 2**30, memory.available / 2**30
    gpu = []
    if shutil.which('nvidia-smi'):
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                                    capture_output=True, text=True, timeout=5, check=True)
            gpu = result.stdout.strip().splitlines()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'ram_gib': round(total, 1), 'available_ram_gib': round(available, 1),
            'nvidia_gpu_and_vram_mib': gpu,
            'free_disk_gib': round(shutil.disk_usage(ROOT).free / 2**30, 1),
            'recommended_ollama_model': recommendation(total, available),
            'note': 'RAM-based starting point. GPU is optional; unlisted GPU is not necessarily absent. '
                    'No downloads or API calls. Keep memory free for CPU Laya, OS and model context.'}


@dataclass(frozen=True)
class ReaderConfig:
    base_url: str
    model: str
    api_key_env: str
    timeout_seconds: int
    backend: str


def validate_config(data, *, allow_cloud=False):
    if set(data) - {'backend', 'base_url', 'model', 'api_key_env', 'timeout_seconds'}:
        raise PlannerError('Unknown config fields. Put credentials only in an environment variable.')
    backend = data.get('backend')
    if backend == 'offline':
        if set(data) != {'backend'}:
            raise PlannerError('Offline config must contain only backend.')
        return None
    if backend not in {'local', 'cloud'}:
        raise PlannerError('Choose offline, local or cloud explicitly.')
    timeout = data.get('timeout_seconds', 120)
    if type(timeout) is not int or not 1 <= timeout <= 180:
        raise PlannerError('Timeout must be an integer from 1 to 180 seconds.')
    model, env = data.get('model'), data.get('api_key_env', '')
    if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise PlannerError('Set an actual model ID.')
    if not isinstance(env, str) or env and (not env.isascii() or not env.isidentifier()):
        raise PlannerError('api_key_env must name an environment variable, never contain a key.')
    try:
        url = urllib.parse.urlsplit(data.get('base_url', ''))
        _ = url.port  # Reject malformed/out-of-range ports before creating a request.
        if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in {'', '/', '/v1', '/v1/'}
                or any(c.isspace() for c in url.netloc)):
            raise ValueError()
    except (TypeError, ValueError):
        raise PlannerError('Use a plain API base URL ending in /v1, without credentials or query.') from None
    base = urllib.parse.urlunsplit((url.scheme, url.netloc, '/v1', '', ''))
    if backend == 'local':
        # Reuse the private-network boundary without changing existing experiment contracts.
        try:
            address = ipaddress.ip_address(url.hostname)
            local = address.is_loopback or any(address in ipaddress.ip_network(network) for network in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10'))
        except ValueError:
            local = url.hostname == 'localhost' or url.hostname.endswith('.ts.net')
        if not local:
            raise PlannerError('Local mode only accepts loopback, private LAN or Tailscale endpoints.')
        if 'cloud' in model.lower():
            raise PlannerError('Cloud-tagged models require explicit cloud mode.')
    else:
        if not allow_cloud:
            raise PlannerError('Cloud mode requires --allow-cloud on every probe/play invocation.')
        if url.scheme != 'https' or not env:
            raise PlannerError('Cloud mode requires HTTPS and an API-key environment variable.')
        try:
            public = ipaddress.ip_address(url.hostname).is_global
        except ValueError:
            public = '.' in url.hostname and not url.hostname.endswith(('.local', '.localhost', '.ts.net'))
        if not public:
            raise PlannerError('Cloud mode requires the public provider hostname.')
    return ReaderConfig(base, model.strip(), env, timeout, backend)


class ReaderPlanner(StrataPlanner):
    def request(self, suffix, body=None):
        if body is not None:
            body = {**body}
            body.pop('reasoning_effort', None)
            body['response_format'] = {'type': 'json_object'}
            body['max_tokens'] = 512
            body['messages'] = [dict(message) for message in body['messages']]
            body['messages'][0]['content'] += ' Exact JSON keys: stage (allowed value), reason (short string).'
            if self.config.backend == 'local':
                body['messages'][0]['content'] += ' /no_think'
        try:
            return super().request(suffix, body)
        except PlannerError as error:
            raise PlannerError(str(error).replace('地端模型', '設定的模型').replace('；未改用雲端模型', '；未切換其他服務')) from None


def load_planner(allow_cloud):
    if not CONFIG.exists():
        raise PlannerError('Run setup first. No backend is selected automatically.')
    cfg = validate_config(strict_object(CONFIG.read_text(encoding='utf-8')), allow_cloud=allow_cloud)
    return ReaderPlanner(cfg) if cfg else None


def setup(args):
    if CONFIG.exists():
        raise PlannerError('.local/reader.json already exists. Edit it intentionally; setup will not overwrite it.')
    if args.backend == 'offline':
        if args.download:
            raise PlannerError('--download is only for local Ollama setup; use download-laya separately.')
        data = {'backend': 'offline'}
    else:
        model = args.model
        if args.backend == 'local' and not model:
            model = hardware()['recommended_ollama_model']
            if not model:
                raise PlannerError('Not enough available RAM for an automatic local recommendation. '
                                   'Use offline mode, explicitly choose cloud, or free memory and retry.')
        data = {'backend': args.backend, 'model': model,
                'base_url': args.base_url or ('http://127.0.0.1:11434/v1' if args.backend == 'local' else ''),
                'api_key_env': args.api_key_env or ('LAYA_PLANNER_API_KEY' if args.backend == 'cloud' else ''),
                'timeout_seconds': args.timeout}
        validate_config(data, allow_cloud=args.allow_cloud)
        if args.download:
            if args.backend != 'local' or data['base_url'] != 'http://127.0.0.1:11434/v1' or model not in {'qwen3:4b', 'qwen3:8b'}:
                raise PlannerError('Automatic download only supports local Ollama qwen3:4b / qwen3:8b.')
            executable = shutil.which('ollama')
            if not executable:
                raise PlannerError('Install Ollama from https://ollama.com/download first.')
            if shutil.disk_usage(ROOT).free < 12 * 2**30:
                raise PlannerError('Keep at least 12 GiB free before downloading. Check the Ollama model volume too.')
            print(f'Downloading {model}; weights about 2.5 GB (4b) or 5.2 GB (8b), additional runtime memory needed.', flush=True)
            subprocess.run([executable, 'pull', model], check=True,
                           env={**os.environ, 'OLLAMA_HOST': '127.0.0.1:11434'})
    CONFIG.parent.mkdir(exist_ok=True)
    with CONFIG.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
    print('Saved .local/reader.json (Git-ignored). Run probe before play.')


def child_environment(config=None):
    env = dict(os.environ)
    if config and config.api_key_env:
        env.pop(config.api_key_env, None)
    env.update(HF_HOME=str(ROOT / '.cache/huggingface'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    return env


def game_command(args, state, strategy, output):
    command = [sys.executable, '-X', 'utf8', '-m', 'laya_pokemon.cli', 'play', '--rom', str(args.rom),
               '--objective', 'Complete the current verified Pokemon Red stage.', '--opening-route',
               '--strategy-file', str(strategy), '--policy', 'laya', '--steps', '300', '--hold-frames', '8',
               '--settle-frames', '32', '--offline', '--video', '--live-view', '--output', str(output)]
    if state:
        command += ['--state', str(state)]
    if args.window:
        command += ['--window']
    if args.fast_forward:
        command += ['--fast-forward']
    return command


def play(args):
    from strata_supervisor import snapshot_from_state
    from serve_live_game import handler_for
    planner = load_planner(args.allow_cloud)
    args.rom = Path(args.rom).resolve(strict=True)
    if parse_rom_header(args.rom)['sha256'] != RED_SHA:
        raise PlannerError('This controller requires the verified English Red revision; see docs/reader-quickstart.md.')
    state = Path(args.state).resolve(strict=True) if args.state else None
    if planner:
        planner.verify_model()
    run = ROOT / 'outputs/reader' / utc_now().replace(':', '-').replace('.', '-')
    run.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'backend': planner.config.backend if planner else 'offline',
              'cloud_opt_in': bool(planner and planner.config.backend == 'cloud'), 'episodes': [],
              'button_backend': 'offline_laya_cpu', 'max_episodes': args.episodes}
    write_json(run / 'summary.json', report)
    print(f'Run: {run.relative_to(ROOT)}', flush=True)
    try:
        for episode in range(args.episodes):
            if state is None:
                decision = {'stage': 'starter', 'source': 'validated_opening'}
            else:
                snapshot = snapshot_from_state(args.rom, state)
                snapshot['mission'] = 'first_gym'
                choices = allowed_stages(snapshot)
                decision = planner.decide(snapshot, choices) if planner else {'stage': choices[0], 'source': 'fixed_controller'}
            if decision['stage'] in {'review', 'stop'}:
                report.update(status='stopped', stop_reason=decision['stage'])
                break
            strategy = run / f'strategy-{episode:02}.json'
            write_json(strategy, {'stage': decision['stage'], 'starter': 'BULBASAUR'})
            game = run / f'game-{episode:02}'
            # Existing viewer exposes only the selected run's status and frame; no directory server.
            server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(game))
            args.port = server.server_port  # Keep the same browser URL for subsequent episodes.
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            print(f'Episode {episode + 1}: http://127.0.0.1:{server.server_port}/ (view only; Ctrl+C stops)', flush=True)
            try:
                with (run / f'game-{episode:02}.log').open('w', encoding='utf-8') as log:
                    process = subprocess.run(game_command(args, state, strategy, game), cwd=ROOT, stdout=log,
                                             stderr=subprocess.STDOUT, env=child_environment(planner.config if planner else None))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            if process.returncode or not (game / 'summary.json').is_file() or not (game / 'final.state').is_file():
                raise PlannerError('Game stopped with an error. Inspect this run locally; no automatic retry/fallback.')
            summary = json.loads((game / 'summary.json').read_text(encoding='utf-8'))
            state = game / 'final.state'
            report['latest_state'] = str(state.relative_to(ROOT))
            report['episodes'].append({'stage': decision['stage'], 'stop_reason': summary.get('stop_reason'),
                                       'usage': decision.get('usage')})
            write_json(run / 'summary.json', report)
            if summary.get('stop_reason') not in {'wall_clock_limit', 'action_budget',
                                                 'capture_milestone', 'training_milestone'}:
                report.update(status='stopped', stop_reason=summary.get('stop_reason'))
                break
        else:
            report.update(status='stopped', stop_reason='episode_budget')
    except BaseException as error:
        report.update(status='stopped', stop_reason='keyboard_interrupt' if isinstance(error, KeyboardInterrupt) else 'error',
                      error_type=type(error).__name__)
        raise
    finally:
        write_json(run / 'summary.json', report)
        print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('recommend', help='Read RAM/GPU information; no network or downloads')
    config = commands.add_parser('setup', help='Select a backend and create Git-ignored configuration')
    config.add_argument('--backend', choices=['offline', 'local', 'cloud'], required=True)
    config.add_argument('--model')
    config.add_argument('--base-url')
    config.add_argument('--api-key-env')
    config.add_argument('--timeout', type=int, default=120)
    config.add_argument('--download', action='store_true', help='Explicitly download the recommended Ollama model')
    config.add_argument('--allow-cloud', action='store_true')
    commands.add_parser('download-laya', help='Explicitly download the fixed public Laya CPU weights')
    probe = commands.add_parser('probe', help='Verify model list plus one synthetic JSON decision; cloud may charge')
    probe.add_argument('--allow-cloud', action='store_true')
    game = commands.add_parser('play', help='Start or resume a bounded recorded game')
    game.add_argument('--rom', required=True)
    game.add_argument('--state')
    game.add_argument('--episodes', type=int, choices=range(1, 21), default=3)
    game.add_argument('--allow-cloud', action='store_true')
    game.add_argument('--window', action='store_true', help='Optional SDL window; default uses loopback browser viewer')
    game.add_argument('--fast-forward', action='store_true')
    game.add_argument('--port', type=int, default=0, help='Loopback viewer port; 0 allocates a free port per episode')
    args = parser.parse_args()
    if args.command == 'recommend':
        print(json.dumps(hardware(), ensure_ascii=False, indent=2))
    elif args.command == 'setup':
        setup(args)
    elif args.command == 'download-laya':
        from huggingface_hub import snapshot_download
        os.environ.setdefault('HF_HOME', str(ROOT / '.cache/huggingface'))
        snapshot_download('convaiinnovations/laya', revision=PINNED_REVISION, token=False,
                          cache_dir=str(ROOT / '.cache/huggingface/hub'),
                          allow_patterns=['*.json', '*.safetensors', 'tokenizer/*'], ignore_patterns=['*/*/*'])
        print('Laya fixed revision downloaded. Gameplay uses offline CPU inference.')
    elif args.command == 'probe':
        planner = load_planner(args.allow_cloud)
        if planner:
            planner.verify_model()
            decision = planner.decide({'test': 'Synthetic connection check; no ROM or real game data.'}, ['review', 'stop'])
            print(json.dumps({'status': 'compatible', 'backend': planner.config.backend, 'stage': decision['stage'],
                              'usage': decision.get('usage')}, indent=2))
        else:
            print('Offline: fixed stage controller + CPU Laya. No reasoning API calls.')
    elif args.command == 'play':
        play(args)


if __name__ == '__main__':
    try:
        main()
    except (PlannerError, OSError, subprocess.SubprocessError) as error:
        # API exceptions have already been redacted. Never print request headers/body.
        print(str(error) if isinstance(error, PlannerError) else f'Operation failed: {type(error).__name__}', file=sys.stderr)
        raise SystemExit(2)
