import os
import sys
import time
import json
import base64
import shutil
import requests
import subprocess
from pathlib import Path


VAULT_ADDR = os.getenv("VAULT_ADDR", "http://vault:8200")
OUTPUT_DIR = "/app/tpm-data"


def run_cmd(cmd, timeout=30, env=None):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env or os.environ.copy()
    )


def check_tpm():
    try:
        result = subprocess.run(
            ['tpm2_getrandom', '4', '--tcti', 'device:/dev/tpmrm0'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def encrypt_with_tpm(data):
    try:
        if isinstance(data, str):
            data = data.encode()

        if check_tpm():
            print("🔐 Usando TPM real para criptografia")

            primary_ctx = "/tmp/primary.ctx"
            aes_pub = "/tmp/aes.pub"
            aes_priv = "/tmp/aes.priv"
            aes_ctx = "/tmp/aes.ctx"
            input_file = "/tmp/tpm_input.bin"
            output_file = "/tmp/tpm_output.bin"

            cleanup_files = [primary_ctx, aes_pub, aes_priv, aes_ctx, input_file, output_file]

            create_primary = subprocess.run([
                'tpm2_createprimary',
                '--tcti', 'device:/dev/tpmrm0',
                '-C', 'o',
                '-c', primary_ctx,
                '-Q'
            ], capture_output=True, timeout=30)

            if create_primary.returncode == 0:
                create_aes = subprocess.run([
                    'tpm2_create',
                    '--tcti', 'device:/dev/tpmrm0',
                    '-C', primary_ctx,
                    '-G', 'aes128cfb',
                    '-u', aes_pub,
                    '-r', aes_priv,
                    '-Q'
                ], capture_output=True, timeout=30)

                if create_aes.returncode == 0:
                    load_aes = subprocess.run([
                        'tpm2_load',
                        '--tcti', 'device:/dev/tpmrm0',
                        '-C', primary_ctx,
                        '-u', aes_pub,
                        '-r', aes_priv,
                        '-c', aes_ctx,
                        '-Q'
                    ], capture_output=True, timeout=30)

                    if load_aes.returncode == 0:
                        with open(input_file, 'wb') as f:
                            f.write(data)

                        encrypt_result = subprocess.run([
                            'tpm2_encryptdecrypt',
                            '--tcti', 'device:/dev/tpmrm0',
                            '-c', aes_ctx,
                            '-o', output_file,
                            input_file
                        ], capture_output=True, timeout=30)

                        if encrypt_result.returncode == 0 and os.path.exists(output_file):
                            with open(output_file, 'rb') as f:
                                encrypted_data = f.read()

                            for temp_file in cleanup_files:
                                if os.path.exists(temp
