"""Refresh the explicit target inventory from authoritative upstream metadata."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import time
import sys
import io
import zipfile
from storage import atomic_json

ROOT = Path(__file__).resolve().parents[2]

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MinecraftTemplate/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 2: raise
            time.sleep(1)

def versions(url):
    return [item.text for item in ET.fromstring(fetch(url)).findall('./versioning/versions/version')]

def numeric(version):
    return tuple(int(value) for value in version.split('.'))

def forge_mdk_major(mc, forge):
    coordinate = f'{mc}-{forge}'
    url = f'https://maven.minecraftforge.net/net/minecraftforge/forge/{coordinate}/forge-{coordinate}-mdk.zip'
    with zipfile.ZipFile(io.BytesIO(fetch(url))) as archive:
        script = archive.read('build.gradle').decode('utf-8')
    match = re.search(r"id\s+['\"]net\.minecraftforge\.gradle['\"]\s+version\s+['\"]\[?(\d+)",script)
    if not match: raise ValueError(f'Unrecognized Forge MDK plugin declaration for {mc}')
    return int(match[1])

def write_new(path, text):
    from template import properties
    metadata = properties(ROOT / 'properties/mod.properties')
    package = metadata['mod.group']+'.'+metadata['mod.id']
    path = Path(str(path).replace(str(Path('dev/example/examplemod')),str(Path(package.replace('.','/')))))
    text = text.replace('dev.example.examplemod','__TEMPLATE_PACKAGE__').replace('examplemod',metadata['mod.id']).replace('__TEMPLATE_PACKAGE__',package)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding='utf-8', newline='\n')

def scaffold(version, loader):
    base = ROOT / 'versions' / version / loader / 'src/main'
    package = 'dev.example.examplemod'
    if loader == 'fabric':
        imports = 'import net.fabricmc.api.ModInitializer;\nimport net.fabricmc.loader.api.FabricLoader;'
        declaration = 'public final class Entrypoint implements ModInitializer'
        body = 'public void onInitialize() {\n        TemplateMod.initialize(new RuntimePlatform("fabric", FabricLoader.getInstance().getConfigDir()));\n    }'
        metadata = '''{
  "schemaVersion": 1,
  "id": "${mod_id}",
  "version": "${mod_version}",
  "name": "${mod_name}",
  "description": "${mod_description}",
  "license": "${mod_license}",
  "environment": "*",
  "entrypoints": { "main": ["dev.example.examplemod.fabric.Entrypoint"] },
  "depends": { "fabricloader": ">=${loader_version}", "minecraft": "${minecraft_version}", "java": ">=${java_release}" }
}
'''
        write_new(base / 'resources/fabric.mod.json', metadata)
    else:
        namespace = 'net.minecraftforge' if loader == 'forge' else 'net.neoforged'
        imports = f'import {namespace}.fml.common.Mod;\nimport {namespace}.fml.loading.FMLPaths;'
        declaration = '@Mod(TemplateMod.MOD_ID)\npublic final class Entrypoint'
        body = f'public Entrypoint() {{\n        TemplateMod.initialize(new RuntimePlatform("{loader}", FMLPaths.CONFIGDIR.get()));\n    }}'
        neo_modern = loader == 'neoforge' and numeric(version) >= (1, 20, 5)
        filename = 'neoforge.mods.toml' if neo_modern else 'mods.toml'
        dependency_id = loader
        required = 'type="required"' if neo_modern else 'mandatory=true'
        metadata = f'''modLoader="javafml"
loaderVersion="[1,)"
license="${{mod_license}}"
[[mods]]
modId="${{mod_id}}"
version="${{mod_version}}"
displayName="${{mod_name}}"
description="${{mod_description}}"
[[dependencies.${{mod_id}}]]
modId="{dependency_id}"
{required}
versionRange="[${{loader_version}},)"
ordering="NONE"
side="BOTH"
[[dependencies.${{mod_id}}]]
modId="minecraft"
{required}
versionRange="[${{minecraft_version}}]"
ordering="NONE"
side="BOTH"
'''
        write_new(base / 'resources/META-INF' / filename, metadata)
    source = f'''package {package}.{loader};

import {package}.TemplateMod;
import {package}.platform.RuntimePlatform;
{imports}

{declaration} {{
    {body}
}}
'''
    write_new(base / 'java/dev/example/examplemod' / loader / 'Entrypoint.java', source)

def refresh():
    manifest_url = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
    manifest = json.loads(fetch(manifest_url))
    releases = [v for v in manifest['versions'] if v['type'] == 'release' and (1,16) <= numeric(v['id']) <= (26,3)]
    releases.sort(key=lambda v: numeric(v['id']))
    promos = json.loads(fetch('https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json'))['promos']
    neo = versions('https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml')
    loader = next(v['version'] for v in json.loads(fetch('https://meta.fabricmc.net/v2/versions/loader')) if v['stable'])
    fabric_games = {v['version'] for v in json.loads(fetch('https://meta.fabricmc.net/v2/versions/game'))}
    forge_plugins = versions('https://maven.minecraftforge.net/net/minecraftforge/gradle/ForgeGradle/maven-metadata.xml')
    fg = max((v for v in forge_plugins if re.fullmatch(r'6\.0\.\d+', v)), key=numeric)
    forge_markers = versions('https://maven.minecraftforge.net/net/minecraftforge/gradle/net.minecraftforge.gradle.gradle.plugin/maven-metadata.xml')
    fg7 = max((v for v in forge_markers if re.fullmatch(r'7\.0\.\d+', v)), key=numeric)
    mdg = versions('https://maven.neoforged.net/releases/net/neoforged/moddev/net.neoforged.moddev.gradle.plugin/maven-metadata.xml')
    mdg_pin = max((v for v in mdg if re.fullmatch(r'2\.0\.\d+', v)), key=numeric)
    ng = versions('https://maven.neoforged.net/releases/net/neoforged/gradle/userdev/maven-metadata.xml')
    ng_pin = max((v for v in ng if re.fullmatch(r'7\.1\.\d+', v)), key=numeric)

    def collect(release):
        version = release['id']
        game = json.loads(fetch(release['url']))
        java = game.get('javaVersion', {}).get('majorVersion', 8)
        fabric_available = version in fabric_games
        props = {'minecraft.version': version, 'java.release': str(java)}
        loaders = []
        if fabric_available:
            loaders.append('fabric')
            props.update({'fabric.version': loader, 'fabric.loom': '1.17.21', 'fabric.profile': 'fabric'})
            props['fabric.mappings'] = 'none' if version.startswith('26.') else 'mojang'
        forge = promos.get(version+'-recommended') or promos.get(version+'-latest')
        if forge:
            loaders.append('forge')
            props.update({'forge.version': forge, 'forge.gradle': fg, 'forge.profile': 'forge', 'forge.mappings.channel': 'official', 'forge.mappings.version': version})
            props['forge.reobfuscate'] = str(numeric(version)<(1,20,6)).lower()
            if numeric(version) >= (1,20,6) and forge_mdk_major(version,forge) == 7:
                props.update({'forge.gradle': fg7, 'forge.profile': 'forge7'})
        parts = numeric(version)
        prefix = None
        if (1,20,2) <= parts < (2,):
            prefix = f'{parts[1]}.{parts[2] if len(parts)>2 else 0}.'
        elif parts >= (26,):
            prefix = version + ('.0.' if len(parts) == 2 else '.')
        candidates = [v for v in neo if prefix and v.startswith(prefix) and re.fullmatch(r'[\d.]+', v)]
        if not candidates:
            candidates = [v for v in neo if prefix and v.startswith(prefix) and re.fullmatch(r'[\d.]+-beta',v)]
        if candidates:
            loaders.append('neoforge')
            modern = parts >= (1,21)
            props.update({'neoforge.version': max(candidates,key=lambda v:numeric(v.removesuffix('-beta'))), 'neoforge.profile': 'neoforge26' if parts >= (26,) else 'neoforge', 'neoforge.plugin': 'net.neoforged.moddev' if modern else 'net.neoforged.gradle.userdev', 'neoforge.gradle': mdg_pin if modern else ng_pin})
        props['loaders'] = ','.join(loaders)
        text = '# Exact upstream pins; run tools/kyro/catalog.py only when intentionally updating.\n'
        text += '\n'.join(f'{k}={v}' for k,v in props.items())+'\n'
        (ROOT / 'properties' / f'{version}.properties').write_text(text, encoding='utf-8', newline='\n')
        write_new(ROOT / 'versions' / version / 'common/src/main/java/.gitkeep', '')
        write_new(ROOT / 'versions' / version / 'common/src/main/resources/.gitkeep', '')
        for target in loaders:
            scaffold(version,target)
        return {'minecraft': version, 'java': java, 'loaders': {name: {'status': 'unverified', 'dependency': props[f'{name}.version']} for name in loaders}, 'unavailable': [name for name in ('fabric','forge','neoforge') if name not in loaders]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        targets = list(pool.map(collect, releases))
    atomic_json(ROOT / 'targets.json',{'schema': 1, 'source': manifest_url, 'targets': targets})
    print(f'Catalogued {len(targets)} releases and {sum(len(t["loaders"]) for t in targets)} loader targets. Build status reset to unverified.')

def add_beta_targets():
    """Add beta-only NeoForge release lines without resetting existing verification."""
    from template import properties
    releases = versions('https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml')
    path = ROOT / 'targets.json'
    catalog = json.loads(path.read_text())
    additions = []
    for target in catalog['targets']:
        mc = target['minecraft']
        if numeric(mc) < (1,20,2) or 'neoforge' in target['loaders']: continue
        parts = numeric(mc)
        prefix = f'{parts[1]}.{parts[2] if len(parts)>2 else 0}.' if parts < (2,) else mc+('.0.' if len(parts)==2 else '.')
        candidates = [v for v in releases if v.startswith(prefix) and re.fullmatch(r'[\d.]+-beta',v)]
        if not candidates: continue
        version = max(candidates,key=lambda v:numeric(v.removesuffix('-beta')))
        modern = parts >= (1,21)
        reference = properties(ROOT / 'properties' / ('1.21.1.properties' if modern else '1.20.2.properties'))
        pins_path = ROOT / 'properties' / f'{mc}.properties'
        pins = properties(pins_path)
        pins['loaders'] += ',neoforge'
        pins.update({key:value for key,value in reference.items() if key.startswith('neoforge.')})
        pins['neoforge.version'] = version
        if parts >= (26,): pins['neoforge.profile'] = 'neoforge26'
        pins_path.write_text('\n'.join(f'{k}={v}' for k,v in pins.items())+'\n',encoding='utf-8')
        scaffold(mc,'neoforge')
        additions.append((mc,version))
    catalog = json.loads(path.read_text())
    for mc,version in additions:
        target = next(t for t in catalog['targets'] if t['minecraft']==mc)
        target['loaders']['neoforge'] = {'status':'unverified','dependency':version}
        target['unavailable'].remove('neoforge')
    atomic_json(path,catalog)
    print(f'Added {len(additions)} beta-only NeoForge release lines.')

def recover():
    """Recover the inventory offline from pinned properties after an interrupted write."""
    from template import properties
    targets = []
    reports = ROOT.parent / (ROOT.name+'-support') / 'verification'
    for path in sorted((ROOT / 'properties').glob('*.properties'),key=lambda p:numeric(p.stem) if p.stem!='mod' else (999,)):
        if path.stem == 'mod': continue
        pins = properties(path)
        loaders = {}
        for loader in pins['loaders'].split(','):
            status = 'unverified'
            report = reports / f'{path.stem}-{loader}.json'
            if report.exists():
                try: status = json.loads(report.read_text())['status']
                except (ValueError,KeyError): pass
            loaders[loader] = {'status':status,'dependency':pins[f'{loader}.version']}
        targets.append({'minecraft':path.stem,'java':int(pins['java.release']),'loaders':loaders,'unavailable':[name for name in ('fabric','forge','neoforge') if name not in loaders]})
    atomic_json(ROOT / 'targets.json',{'schema':1,'source':'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json','targets':targets})
    print('Recovered inventory from pinned properties and saved build evidence.')

def official_mappings():
    from template import properties
    changed = []
    for path in (ROOT / 'properties').glob('*.properties'):
        if path.stem == 'mod': continue
        pins = properties(path)
        if 'fabric' not in pins['loaders'].split(','): continue
        provider = 'none' if path.stem.startswith('26.') else 'mojang'
        if pins.get('fabric.mappings') == provider: continue
        pins['fabric.mappings'] = provider
        path.write_text('\n'.join(f'{k}={v}' for k,v in pins.items())+'\n',encoding='utf-8')
        if provider == 'mojang': changed.append(path.stem)
    path = ROOT / 'targets.json'
    catalog = json.loads(path.read_text())
    for target in catalog['targets']:
        if target['minecraft'] in changed:
            target['loaders']['fabric']['status'] = 'unverified'
    atomic_json(path,catalog)
    print(f'Aligned {len(changed)} obfuscated Fabric targets to official Mojang mappings; verification reset for affected targets.')

def forge_mdks():
    from template import properties
    plugins = versions('https://maven.minecraftforge.net/net/minecraftforge/gradle/net.minecraftforge.gradle.gradle.plugin/maven-metadata.xml')
    latest = {major:max((v for v in plugins if re.fullmatch(fr'{major}\.0\.\d+',v)),key=numeric) for major in (6,7)}
    changed = []
    for path in (ROOT / 'properties').glob('*.properties'):
        if path.stem == 'mod' or numeric(path.stem)<(1,20,6): continue
        pins = properties(path)
        if 'forge' not in pins['loaders'].split(','): continue
        major = forge_mdk_major(path.stem,pins['forge.version'])
        if major not in latest: raise ValueError(f'Unsupported ForgeGradle major: {major}')
        plugin,profile = latest[major],'forge7' if major==7 else 'forge'
        if pins['forge.gradle'] != plugin or pins['forge.profile'] != profile or pins.get('forge.reobfuscate') != 'false':
            pins.update({'forge.gradle':plugin,'forge.profile':profile,'forge.reobfuscate':'false'})
            path.write_text('\n'.join(f'{k}={v}' for k,v in pins.items())+'\n',encoding='utf-8')
            changed.append(path.stem)
        print(f'Forge {path.stem}: official MDK uses ForgeGradle {major}',flush=True)
    path = ROOT / 'targets.json'
    catalog = json.loads(path.read_text())
    for target in catalog['targets']:
        if target['minecraft'] in changed: target['loaders']['forge']['status']='unverified'
    atomic_json(path,catalog)

if __name__ == '__main__':
    if '--recover' in sys.argv: recover()
    elif '--add-beta-targets' in sys.argv: add_beta_targets()
    elif '--official-mappings' in sys.argv: official_mappings()
    elif '--forge-mdks' in sys.argv: forge_mdks()
    else: refresh()
