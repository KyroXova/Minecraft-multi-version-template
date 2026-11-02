"""Download a checksum-verified Temurin Windows x64 JDK without a system installer."""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request
import zipfile
from catalog import fetch

def install(major,destination):
    destination = destination.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    metadata = json.loads(fetch(f'https://api.github.com/repos/adoptium/temurin{major}-binaries/releases/latest'))
    package = next(a for a in metadata['assets'] if 'jdk_x64_windows_hotspot' in a['name'] and a['name'].endswith('.zip'))
    checksum = next(a for a in metadata['assets'] if a['name']==package['name']+'.sha256.txt')
    expected = fetch(checksum['browser_download_url']).decode().split()[0]
    archive = destination / package['name']
    if not archive.exists():
        urllib.request.urlretrieve(package['browser_download_url'],archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise ValueError('JDK checksum verification failed')
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            if not (destination / member.filename).resolve().is_relative_to(destination):
                raise ValueError('Archive path escapes JDK destination')
            if member.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('JDK archive contains a symbolic link')
        zipped.extractall(destination)
    home = next(destination.glob('*/bin/java.exe')).parent.parent
    print(home)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version',type=int,required=True,choices=[8,16,17,21,25])
    parser.add_argument('--destination',type=Path,required=True)
    args = parser.parse_args()
    install(args.version,args.destination)
