"""Verify release assets and checksums without creating a release."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import zipfile


root = Path(__file__).resolve().parents[1]
workflow = (root / '.github/workflows/sashimi_build-bangkk.yml').read_text()
step = workflow.split('      - name: Prepare Release Artifacts\n', 1)[1]
program = textwrap.dedent(step.split("python3 - <<'PY'\n", 1)[1].split('\n          PY', 1)[0])
cases = [(branch, ksu, susfs) for branch in ('seventeen', 'eevdf')
         for ksu, susfs in ((False, False), (True, False), (True, True))]

for branch, ksu, susfs in cases:
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        kernel = work / 'android_kernel_motorola_sm6375'
        boot = kernel / 'out/arch/arm64/boot'
        boot.mkdir(parents=True)
        image = b'fixture Image\n'
        (boot / 'Image').write_bytes(image)
        config = ('CONFIG_KSU=y\n' if ksu else '# CONFIG_KSU is not set\n')
        config += ('CONFIG_KSU_SUSFS=y\n' if susfs else
                   'CONFIG_KSU_MANUAL_HOOK=y\n' if ksu else '')
        (kernel / 'out/.config').write_text(config)
        info = json.dumps({'kernel_branch': branch, 'sha256': {
            '.config': hashlib.sha256(config.encode()).hexdigest()}}).encode()
        (kernel / 'out/build-info.json').write_bytes(info)
        prefix = 'Sashimi' + ('-eevdf' if branch == 'eevdf' else '')
        prefix += '-ksu' if ksu else ''
        prefix += '-susfs' if susfs else ''
        name = prefix + '-20261112-1200-bangkk.zip'
        with zipfile.ZipFile(kernel / name, 'w') as package:
            package.writestr('Image', image)
        if ksu:
            manager = work / 'CI/Manager/BakaSU_Manager.apk'
            manager.parent.mkdir(parents=True)
            manager.write_bytes(b'fixture manager')
        environment = dict(os.environ, BUILD_KSU=str(ksu).lower(),
                           BUILD_SUSFS=str(susfs).lower(), ZIP_NAME=name,
                           CREATE_RELEASE='true', BRANCH=branch,
                           SERVER_URL='https://github.com', REPO='fixture/CI',
                           RELEASE_TAG='fixture', DATE_STR='12.11.26',
                           GITHUB_STEP_SUMMARY=str(work / 'summary'))
        result = subprocess.run(['python3', '-c', program], cwd=work,
                                env=environment, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        output = work / 'release_out'
        assert (output / 'kernel.config').read_text() == config
        assert (output / 'build-info.json').read_bytes() == info
        assert (output / name).read_bytes() == (kernel / name).read_bytes()
        expected = {name, 'kernel.config', 'build-info.json'}
        if ksu:
            expected.add('BakaSU_Manager.apk')
        checksums = dict(line.split('  ', 1)[::-1] for line in
                         (output / 'SHA256SUMS').read_text().splitlines())
        assert set(checksums) == expected
        for filename, checksum in checksums.items():
            assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == checksum
        with zipfile.ZipFile(output / name) as package:
            assert set(package.namelist()) == {'Image'}

print(f'PASS: {len(cases)} release fixtures; separate configuration/provenance and complete checksums')
