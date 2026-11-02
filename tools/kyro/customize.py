"""Rename a fresh template consistently, including adapter packages and metadata."""
from pathlib import Path
import argparse
import json
import re
from storage import atomic_json
from template import ROOT, properties

def customize(mod_id, group, name, version):
    keywords = set('abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null'.split())
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}',mod_id):
        raise ValueError('Mod ID must be 2–64 lowercase letters, digits, or underscores, starting with a letter.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+',group):
        raise ValueError('Group must be a lowercase dotted Java package.')
    if mod_id in keywords or any(part in keywords for part in group.split('.')):
        raise ValueError('Java package components cannot be reserved keywords.')
    if not name.strip() or not re.fullmatch(r'[0-9][0-9A-Za-z.+_-]*',version):
        raise ValueError('Provide a nonempty name and a version starting with a digit, without spaces or path separators.')
    if any(c in name+version for c in '\n\r\\"$'):
        raise ValueError('Name/version cannot contain newlines, backslashes, quotes, or dollar signs.')
    metadata = properties(ROOT / 'properties/mod.properties')
    old_id = metadata['mod.id']
    old_package = metadata['mod.group']+'.'+old_id
    package = group+'.'+mod_id
    edits = []
    for directory in ('common','versions','build-logic'):
        for source in (ROOT / directory).rglob('*'):
            if source.is_file() and source.suffix in ('.java','.json','.toml','.gradle'):
                content = source.read_text(encoding='utf-8')
                replacement = content.replace(old_package,'__TEMPLATE_PACKAGE__').replace(old_id,mod_id).replace('__TEMPLATE_PACKAGE__',package).replace(metadata['mod.name'],name)
                relative = source.relative_to(ROOT).as_posix()
                destination = ROOT / relative.replace(old_package.replace('.','/'),package.replace('.','/'))
                assert destination.resolve().is_relative_to(ROOT.resolve())
                if destination != source and destination.exists():
                    raise ValueError(f'Destination already exists: {destination}')
                edits.append((source,destination,replacement))
    for source,destination,content in edits:
        source.write_text(content,encoding='utf-8',newline='\n')
        if source != destination:
            destination.parent.mkdir(parents=True,exist_ok=True)
            source.rename(destination)
    metadata.update({'mod.id':mod_id,'mod.group':group,'mod.name':name,'mod.version':version})
    (ROOT / 'properties/mod.properties').write_text('\n'.join(f'{key}={value}' for key,value in metadata.items())+'\n',encoding='utf-8')
    catalog_path = ROOT / 'targets.json'
    catalog = json.loads(catalog_path.read_text())
    for target in catalog['targets']:
        for loader in target['loaders'].values():
            loader['status'] = 'unverified'
    atomic_json(catalog_path,catalog)
    print(f'Configured {package}. Rebuild the core and selected targets before release.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id',required=True)
    parser.add_argument('--group',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--version',default='1.0.0')
    args = parser.parse_args()
    customize(args.id,args.group,args.name,args.version)
