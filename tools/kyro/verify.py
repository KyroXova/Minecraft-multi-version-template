"""Build the explicit target matrix and retain per-target evidence outside the repository."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import zipfile
import xml.etree.ElementTree as ET
from template import ROOT, inventory, properties, validate
from storage import atomic_json, require_space
from resources import worker_budget

WRITE_LOCK = threading.Lock()

def inspect_artifact(mc, loader):
    metadata = properties(ROOT / 'properties/mod.properties')
    directory = ROOT / 'build' / mc / loader
    jar = directory / 'libs' / f'{metadata["mod.id"]}-{mc}-{loader}-{metadata["mod.version"]}.jar'
    with zipfile.ZipFile(jar) as archive:
        names = archive.namelist()
        package = metadata['mod.group'].replace('.','/')+'/'+metadata['mod.id']
        assert package+'/TemplateMod.class' in names, 'Shared initializer missing'
        assert package+f'/{loader}/Entrypoint.class' in names, 'Loader entrypoint missing'
        target_java = int(properties(ROOT / 'properties' / f'{mc}.properties')['java.release'])
        for name in (package+'/TemplateMod.class',package+f'/{loader}/Entrypoint.class'):
            assert int.from_bytes(archive.read(name)[6:8],'big') == target_java+44, 'Incorrect Java bytecode target'
        assert not any(name.endswith('.java') for name in names), 'Sources in production JAR'
        resource = 'fabric.mod.json' if loader == 'fabric' else next(n for n in names if n in ('META-INF/mods.toml','META-INF/neoforge.mods.toml'))
        content = archive.read(resource).decode()
        assert '${' not in content, 'Unexpanded metadata'
        if loader == 'fabric':
            data = json.loads(content)
            assert data['id'] == metadata['mod.id']
            assert data['depends']['minecraft'] == mc
        else:
            import tomllib
            data = tomllib.loads(content)
            assert data['mods'][0]['modId'] == metadata['mod.id']
    suites = [ET.parse(path).getroot() for path in (directory / 'test-results/test').glob('TEST-*.xml')]
    assert suites, 'Test reports missing'
    assert sum(int(s.get('failures','0'))+int(s.get('errors','0')) for s in suites) == 0
    return {'jar': str(jar.relative_to(ROOT)), 'sha256': hashlib.sha256(jar.read_bytes()).hexdigest(), 'tests': sum(int(s.get('tests','0')) for s in suites)}

def verify_target(mc, loader, report_dir, update_catalog=True):
    log = report_dir / 'logs' / f'{mc}-{loader}.log'
    command = [sys.executable, str(ROOT / 'tools/kyro/template.py'), 'gradle',f'-Pmc={mc}',f'-Ploader={loader}','build']
    with log.open('w',encoding='utf-8') as output:
        result = subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
    evidence = {'minecraft':mc,'loader':loader,'exit_code':result.returncode,'log':str(log),'checked_at':datetime.now(timezone.utc).isoformat()}
    try:
        if result.returncode:
            raise AssertionError('Gradle build failed; see log')
        evidence.update(inspect_artifact(mc,loader))
        evidence['status'] = 'build-verified'
    except (AssertionError, OSError, StopIteration, ValueError) as error:
        evidence.update(status='failed',error=str(error))
    with WRITE_LOCK:
        if update_catalog:
            catalog_path = ROOT / 'targets.json'
            catalog = json.loads(catalog_path.read_text())
            target = next(t for t in catalog['targets'] if t['minecraft']==mc)['loaders'][loader]
            target['status'] = evidence['status']
            atomic_json(catalog_path,catalog)
        atomic_json(report_dir / f'{mc}-{loader}.json',evidence)
        if evidence['status']=='build-verified' and os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as output:
                output.write('jar='+evidence['jar'].replace('\\','/')+'\n')
        print(f'{evidence["status"]}: {mc}/{loader}',flush=True)
    return evidence

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=2,choices=range(1,5))
    parser.add_argument('--target',action='append',help='minecraft/loader; repeat for selected targets')
    parser.add_argument('--resume',action='store_true',help='Skip targets already marked build-verified')
    parser.add_argument('--audit-only',action='store_true',help='Inspect existing production JARs and test reports without rebuilding')
    parser.add_argument('--no-catalog-update',action='store_true',help='Write isolated evidence without updating shared inventory')
    parser.add_argument('--merge-reports',type=Path,action='append',help='Consolidate completed parallel batches after checking artifact hashes')
    parser.add_argument('--report-dir',type=Path,default=ROOT.parent / (ROOT.name+'-support') / 'verification')
    args = parser.parse_args()
    validate()
    report_dir = args.report_dir.resolve()
    assert not report_dir.is_relative_to(ROOT), 'Reports must stay outside the repository'
    (report_dir / 'logs').mkdir(parents=True,exist_ok=True)
    available = [(t['minecraft'],loader) for t in inventory() for loader in t['loaders']]
    selected = [tuple(t.split('/')) for t in args.target] if args.target else available
    if args.merge_reports:
        latest = {}
        for directory in args.merge_reports:
            for path in directory.glob('*.json'):
                record = json.loads(path.read_text(encoding='utf-8'))
                if not all(key in record for key in ('minecraft','loader','status','checked_at')): continue
                key = (record['minecraft'],record['loader'])
                if key not in latest or record['checked_at']>latest[key]['checked_at']: latest[key]=record
        catalog_path = ROOT / 'targets.json'
        catalog = json.loads(catalog_path.read_text())
        consolidated = []
        for target in catalog['targets']:
            for loader,details in target['loaders'].items():
                key = (target['minecraft'],loader)
                record = latest.get(key)
                if not record or record['status']!='build-verified':
                    raise ValueError(f'Missing successful build evidence: {key}')
                actual = inspect_artifact(*key)
                if actual['sha256']!=record['sha256']:
                    raise ValueError(f'Build evidence does not match current artifact: {key}')
                details['status']='build-verified'
                consolidated.append({**record,**actual})
        atomic_json(catalog_path,catalog)
        atomic_json(report_dir / 'consolidated.json',{'passed':len(consolidated),'failed':0,'results':consolidated})
        print(f'Consolidated and audited {len(consolidated)} successful target builds.')
        return 0
    if args.resume:
        completed = {(t['minecraft'],loader) for t in inventory() for loader,details in t['loaders'].items() if details['status']=='build-verified'}
        selected = [t for t in selected if t not in completed]
    assert all(t in available for t in selected), 'Unknown target'
    if args.audit_only:
        results = []
        for mc,loader in selected:
            try:
                results.append({'minecraft':mc,'loader':loader,'status':'passed',**inspect_artifact(mc,loader)})
            except (AssertionError,OSError,StopIteration,ValueError) as error:
                results.append({'minecraft':mc,'loader':loader,'status':'failed','error':str(error)})
        failed = sum(r['status']=='failed' for r in results)
        atomic_json(report_dir / 'artifact-audit.json',{'passed':len(results)-failed,'failed':failed,'results':results})
        print(f'Artifact audit: {len(results)-failed} passed, {failed} failed.')
        return bool(failed)
    metadata = properties(ROOT / 'properties/mod.properties')
    cached = sum((ROOT / 'build' / mc / loader / 'libs' / f'{metadata["mod.id"]}-{mc}-{loader}-{metadata["mod.version"]}.jar').is_file() for mc,loader in selected)
    require_space(len(selected),cached)
    with ThreadPoolExecutor(max_workers=worker_budget(args.workers)) as pool:
        futures = [pool.submit(verify_target,mc,loader,report_dir,not args.no_catalog_update) for mc,loader in selected]
        evidence = [future.result() for future in as_completed(futures)]
    summary = {'passed':sum(e['status']=='build-verified' for e in evidence),'failed':sum(e['status']=='failed' for e in evidence),'results':evidence}
    atomic_json(report_dir / 'summary.json',summary)
    print(f'Build verification: {summary["passed"]} passed, {summary["failed"]} failed.',flush=True)
    return bool(summary['failed'])

if __name__ == '__main__': sys.exit(main())
