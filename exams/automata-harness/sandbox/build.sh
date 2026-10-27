#!/bin/sh
# Explicit small context: no checkout, Git objects, keys, host HOME or auth files.
set -eu
if [ "$#" -ne 2 ]; then
    printf 'usage: sh build.sh NEW_BUILD_DIRECTORY LOCAL_IMAGE_TAG\n' >&2
    exit 2
fi
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$here/../../.." && pwd)
python3 - "$repo" "$here" "$1" <<'PY'
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
repo, here, output = map(pathlib.Path, sys.argv[1:])
output = output.absolute()
output.mkdir(parents=True, mode=0o700, exist_ok=False)
resources = output / 'resources/automata'
resources.mkdir(parents=True)
paths = subprocess.check_output([
    'git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others',
    '--exclude-standard', '--', 'src/automata',
]).decode().split('\0')
records = []
for name in sorted(p for p in paths if p):
    path = repo / name
    if path.is_symlink() or any(part in {'.git', '.agents', 'node_modules', '__pycache__'} for part in path.relative_to(repo).parts):
        raise SystemExit('refusing non-source resource')
    target = resources / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    records.append(name.encode() + b'\0' + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b'\n')
shutil.copyfile(repo / 'README.md', resources / 'README.md')
identity = {
    'git_commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip(),
    'source_sha256': hashlib.sha256(b''.join(records)).hexdigest(),
    'source_files': len(records),
    'asset_source': 'source-projection',
    'readme_sha256': hashlib.sha256((resources / 'README.md').read_bytes()).hexdigest(),
    'pi_version': '1.4.0',
    'profile': 'podman-pilot-standalone-v2',
}
(resources / 'RESOURCE-FINGERPRINT.json').write_text(json.dumps(identity, indent=2) + '\n')
shutil.copyfile(here / 'Containerfile', output / 'Containerfile')
print(json.dumps({'build_context': str(output), 'resources': identity}))
PY
podman build --pull=never --rm=true --force-rm=true \
    --iidfile "$1/image.id" --tag "$2" --file "$1/Containerfile" "$1"
