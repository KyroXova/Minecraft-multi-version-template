"""Seed ForgeGradle 6's library cache from checksum-verified Mojang metadata."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import os
import uuid
from catalog import fetch
from storage import cache_home

def seed(version, workers=8):
    manifest = json.loads(fetch('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
    release = next(v for v in manifest['versions'] if v['id']==version and v['type']=='release')
    metadata = json.loads(fetch(release['url']))
    artifacts = {}
    for library in metadata['libraries']:
        downloads = library.get('downloads',{})
        for artifact in [downloads.get('artifact'),*downloads.get('classifiers',{}).values()]:
            if artifact: artifacts[artifact['path']] = artifact
    directory = cache_home() / 'caches/forge_gradle/maven_downloader'
    directory.mkdir(parents=True,exist_ok=True)
    directory = directory.resolve()

    def download(artifact):
        destination = (directory / artifact['path']).resolve()
        if not destination.is_relative_to(directory): raise ValueError('Library path escapes cache')
        destination.parent.mkdir(parents=True,exist_ok=True)
        valid = destination.is_file() and hashlib.sha1(destination.read_bytes()).hexdigest()==artifact['sha1']
        if not valid:
            data = fetch(artifact['url'])
            if len(data)!=artifact['size'] or hashlib.sha1(data).hexdigest()!=artifact['sha1']:
                raise ValueError(f'Library verification failed: {artifact["path"]}')
            temporary = destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(data)
            os.replace(temporary,destination)
        # ForgeGradle uses a local MD5 sidecar to avoid probing every Maven mirror.
        destination.with_name(destination.name+'.md5').write_text(hashlib.md5(destination.read_bytes()).hexdigest(),encoding='ascii')
        return not valid

    with ThreadPoolExecutor(max_workers=workers) as pool:
        downloaded = sum(pool.map(download,artifacts.values()))
    print(f'Validated {len(artifacts)} Mojang libraries for {version}; downloaded {downloaded}.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('version')
    parser.add_argument('--workers',type=int,default=8,choices=range(1,17))
    args = parser.parse_args()
    seed(args.version,args.workers)
