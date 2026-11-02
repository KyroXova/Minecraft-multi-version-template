"""Export only Git-indexed template files, excluding local caches and build artifacts."""
from pathlib import Path
import argparse
import subprocess
import zipfile
from template import ROOT, validate

def export(destination):
    validate()
    destination = destination.resolve()
    if destination.is_relative_to(ROOT.resolve()):
        raise ValueError('Export destination must be outside the template repository.')
    if destination.exists():
        raise ValueError('Choose a new filename; the export does not overwrite existing archives.')
    paths = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as archive:
        for relative in filter(None,paths):
            path = ROOT / relative
            if not path.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError('Indexed file escapes template root.')
            archive.write(path,ROOT.name+'/'+relative)
    print(f'Exported {destination}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    export(parser.parse_args().destination)
