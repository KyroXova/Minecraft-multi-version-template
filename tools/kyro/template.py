"""Target selection, structural validation, and checksum-pinned Gradle execution."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
from storage import cache_home

ROOT = Path(__file__).resolve().parents[2]

def properties(path):
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith(('#','!')):
            key, value = line.split('=',1)
            result[key.strip()] = value.strip()
    return result

def inventory():
    return json.loads((ROOT / 'targets.json').read_text(encoding='utf-8'))['targets']

def selected(arguments):
    mc, loader = '1.20.1', 'fabric'
    for argument in arguments:
        if argument.startswith('-Pmc='): mc = argument.partition('=')[2]
        if argument.startswith('-Ploader='): loader = argument.partition('=')[2]
    target = next((t for t in inventory() if t['minecraft'] == mc), None)
    if target is None or loader not in target['loaders']:
        raise ValueError(f'Unavailable target: {mc}/{loader}. Run: python tools/kyro/template.py list')
    return mc, loader, properties(ROOT / 'properties' / f'{mc}.properties')

def gradle(arguments):
    if '-Pcore=true' in arguments:
        mc, loader, pins, profile = 'core','core',{},'forge'
    else:
        mc, loader, pins = selected(arguments)
        profile = pins[f'{loader}.profile']
    profiles = json.loads((ROOT / 'gradle/profiles.json').read_text())
    config = profiles[profile]
    env = dict(os.environ)
    local = properties(ROOT / 'local.properties') if (ROOT / 'local.properties').is_file() else {}
    for major in (8,16,17,21,25):
        if f'java.{major}.home' in local:
            env[f'JAVA_{major}_HOME'] = local[f'java.{major}.home']
    java_home = env.get(f'JAVA_{config["java"]}_HOME') or env.get('JAVA_HOME')
    executable = Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java') if java_home else Path('java')
    version = subprocess.run([str(executable),'-version'],capture_output=True,text=True)
    match = re.search(r'version "(?:1\.)?(\d+)',version.stderr+version.stdout)
    if not match or int(match[1]) != config['java']:
        raise ValueError(f'{profile} requires JDK {config["java"]}. Set JAVA_{config["java"]}_HOME or JAVA_HOME.')
    jar = ROOT / 'gradle/wrappers' / profile / 'gradle/wrapper/gradle-wrapper.jar'
    actual = hashlib.sha256(jar.read_bytes()).hexdigest()
    if actual != config['wrapper_sha256']:
        raise ValueError('Gradle wrapper checksum mismatch')
    env['GRADLE_USER_HOME'] = str(cache_home())
    if java_home: env['JAVA_HOME'] = java_home
    project_root = ROOT / '.gradle/build-roots' / mc / loader
    project_root.mkdir(parents=True,exist_ok=True)
    (project_root / 'settings.gradle').write_text("rootProject.name = 'minecraft-mod-template'\n",encoding='utf-8')
    (project_root / 'build.gradle').write_bytes((ROOT / 'build-logic/target.gradle').read_bytes())
    (project_root / 'gradle.properties').write_bytes((ROOT / 'gradle.properties').read_bytes())
    command = [str(executable),'-classpath',str(jar),'org.gradle.wrapper.GradleWrapperMain','-p',str(project_root),f'-PtemplateRoot={ROOT}',*arguments]
    process = subprocess.Popen(command,cwd=ROOT,env=env)
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(int(process._handle), 0x00004000)
        except (AttributeError,OSError):
            pass
    return process.wait()

def validate():
    targets = inventory()
    assert 'tools/kyro/template.py' in (ROOT / 'modw').read_text(), 'Root shell launcher must select a target'
    assert 'tools\\kyro\\template.py' in (ROOT / 'modw.bat').read_text(), 'Root Windows launcher must select a target'
    assert (ROOT / 'build-logic/target.gradle').is_file(), 'Central target build script missing'
    metadata = properties(ROOT / 'properties/mod.properties')
    package = metadata['mod.group']+'.'+metadata['mod.id']
    package_path = Path(package.replace('.','/'))
    profiles = json.loads((ROOT / 'gradle/profiles.json').read_text())
    assert hashlib.sha256((ROOT / 'gradle/wrapper/gradle-wrapper.jar').read_bytes()).hexdigest() == profiles['fabric']['wrapper_sha256'], 'Root wrapper checksum mismatch'
    assert properties(ROOT / 'gradle/wrapper/gradle-wrapper.properties')['distributionSha256Sum'] == properties(ROOT / 'gradle/wrappers/fabric/gradle/wrapper/gradle-wrapper.properties')['distributionSha256Sum']
    for profile, config in profiles.items():
        directory = ROOT / 'gradle/wrappers' / profile / 'gradle/wrapper'
        assert hashlib.sha256((directory / 'gradle-wrapper.jar').read_bytes()).hexdigest() == config['wrapper_sha256'], profile
        wrapper = properties(directory / 'gradle-wrapper.properties')
        assert re.fullmatch(r'[a-f0-9]{64}',wrapper['distributionSha256Sum']), profile
    assert len({t['minecraft'] for t in targets}) == len(targets), 'Duplicate versions'
    assert not targets or targets[0]['minecraft'] == '1.16'
    common = list((ROOT / 'common/src/main/java').rglob('*.java'))
    for source in common:
        assert not re.search(r'import\s+(net\.minecraft|net\.fabricmc|net\.minecraftforge|net\.neoforged)',source.read_text()), source
    for target in targets:
        mc = target['minecraft']
        pins = properties(ROOT / 'properties' / f'{mc}.properties')
        assert set(pins['loaders'].split(',')) == set(target['loaders'])
        assert int(pins['java.release']) == target['java']
        for loader in target['loaders']:
            assert pins[f'{loader}.profile'] in profiles
            base = ROOT / 'versions' / mc / loader / 'src/main'
            sources = common + list((ROOT / 'versions' / mc / 'common/src/main/java').rglob('*.java')) + list((base / 'java').rglob('*.java'))
            classes = []
            for source in sources:
                text = source.read_text()
                source_package = re.search(r'package\s+([\w.]+);',text)[1]
                classes.append(source_package+'.'+source.stem)
            assert len(classes) == len(set(classes)), f'Duplicate classes: {mc}/{loader}'
            assert (base / 'java' / package_path / loader / 'Entrypoint.java').is_file()
            resource_paths = set()
            for resource_root in [ROOT / 'common/src/main/resources', ROOT / 'versions' / mc / 'common/src/main/resources',base / 'resources']:
                for file in resource_root.rglob('*'):
                    if file.is_file() and file.name != '.gitkeep':
                        relative = file.relative_to(resource_root).as_posix()
                        assert relative not in resource_paths, f'Duplicate resource {mc}/{loader}/{relative}'
                        resource_paths.add(relative)
            if loader == 'fabric':
                data = json.loads((base / 'resources/fabric.mod.json').read_text())
                assert data['entrypoints']['main'] == [package+'.fabric.Entrypoint']
            else:
                import tomllib
                metadata_file = next((base / 'resources/META-INF').glob('*.toml'))
                tomllib.loads(metadata_file.read_text().replace('${mod_id}','validationmod'))
    print(f'PASS: {len(targets)} releases, {sum(len(t["loaders"]) for t in targets)} targets; source isolation, metadata, duplicate classes/resources, property consistency.')

def main():
    command = sys.argv[1] if len(sys.argv)>1 else 'validate'
    if command == 'validate': validate()
    elif command == 'list':
        for target in inventory(): print(target['minecraft']+': '+', '.join(target['loaders']))
    elif command == 'gradle': return gradle(sys.argv[2:])
    elif command == 'core': return gradle(['-Pcore=true','build',*sys.argv[2:]])
    else: raise ValueError('Commands: validate, list, gradle')
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError,AssertionError) as error:
        print(f'ERROR: {error}',file=sys.stderr)
        sys.exit(1)
