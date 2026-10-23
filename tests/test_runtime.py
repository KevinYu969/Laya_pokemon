import subprocess
import sys


def test_offline_runtime_blocks_network_before_connection_in_child_process():
    source = '''
import os
import socket
from laya_pokemon.runtime import enable_offline_runtime
enable_offline_runtime()
assert os.environ['HF_HUB_OFFLINE'] == '1'
assert os.environ['TRANSFORMERS_OFFLINE'] == '1'
for operation in (lambda: socket.getaddrinfo('127.0.0.1', 9),
                  lambda: socket.socket().connect(('127.0.0.1', 9)),
                  lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('127.0.0.1', 9))):
    try:
        operation()
    except RuntimeError as error:
        assert '離線模式' in str(error)
    else:
        raise AssertionError('network was not denied')
'''
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
