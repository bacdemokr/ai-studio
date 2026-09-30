"""Produce a small image-based release kit without requiring a source checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def bundle(image, version, output, archive=None):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?', version):
        raise ValueError('Use a new release version, such as 0.1.0-rc.1.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9./:_@-]+', image):
        raise ValueError('Use an explicit image reference, without shell expressions.')
    if image.startswith('ghcr.io/') and not re.search(r'@sha256:[a-f0-9]{64}$', image):
        raise ValueError('Published kits must select the immutable image digest.')
    if archive is not None and not re.fullmatch(r'[a-zA-Z0-9._-]+\.tar(?:\.gz)?', archive):
        raise ValueError('Use an image archive filename without directories.')
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose an empty directory; existing releases are not overwritten.')
    output.mkdir(parents=True, exist_ok=True)
    compose = (ROOT/'compose.yaml').read_text()
    # `compose config` expands shared/ to a build-machine path; keep it portable.
    compose, count = re.subn(r'^  build:\n(?:    .*\n)+', '', compose, count=1, flags=re.M)
    if count != 1 or re.search(r'^\s+build:', compose, re.M):
        raise ValueError('Compose build layout changed; review kit generation.')
    compose = compose.replace('${BAC_IMAGE:-bac-studio:dev}', '${BAC_IMAGE:?Use the supplied .env}')
    (output/'compose.yaml').write_text(compose)
    (output/'.env').write_text('BAC_IMAGE='+image+'\nBAC_VERSION='+version+'\n')
    # App code travels separately from the stable dependency image.
    for name in ('scripts', 'src', 'crew', 'skills', 'docker'):
        shutil.copytree(ROOT/name, output/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(ROOT/'Dockerfile', output/'Dockerfile')
    (output/'api.cfg').write_text('')
    (output/'api.cfg').chmod(0o600)
    shutil.copy2(ROOT/'bac', output/'bac')
    (output/'bac').chmod(0o755)
    if archive:
        (output/'image-archive.txt').write_text(archive+'\n')
    shutil.copyfile(ROOT/'docs/docker-setup.md', output/'README.md')
    shutil.copyfile(ROOT/'docker/runtime-lock.json', output/'runtime-lock.json')
    shutil.copyfile(ROOT/'scripts/container_remove.py', output/'remove.py')
    (output/'shared').mkdir()
    (output/'shared/README.txt').write_text('Place files here, then refer to /host-files/FILENAME in the studio.\n')
    (output/'release.json').write_text(json.dumps({'version': version, 'image': image,
        'runtimeLockSHA256': hashlib.sha256((output/'runtime-lock.json').read_bytes()).hexdigest(),
        'validation': 'See the release verification report; kit generation is not acceptance.'}, indent=2)+'\n')
    # A release must be readable by the unprivileged container UID, including
    # assets generated on a host with restrictive umask. Do not copy host modes.
    for item in output.rglob('*'):
        item.chmod(0o755 if item.is_dir() or item.stat().st_mode & 0o111 else 0o644)
    checksums = ['{}  {}'.format(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(output))
                 for p in sorted(output.rglob('*')) if p.is_file()]
    (output/'SHA256SUMS').write_text('\n'.join(checksums)+'\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--archive', help='Optional image archive shipped beside bac; finalize SHA256SUMS after exporting it')
    args = parser.parse_args()
    print(bundle(args.image, args.version, args.output, args.archive))
