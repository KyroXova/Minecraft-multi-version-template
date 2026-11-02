"""Install official Gradle wrappers with upstream-published SHA-256 verification."""
from pathlib import Path
import hashlib
from catalog import fetch
from storage import atomic_json
import shutil

ROOT = Path(__file__).resolve().parents[2]

def install():
    profiles = {'fabric': ('9.6.0',25), 'forge': ('8.8',21), 'forge7': ('9.7.1',25), 'neoforge': ('8.14.3',21), 'neoforge26': ('9.6.0',25)}
    result = {}
    for name, (version,java) in profiles.items():
        distribution = f'https://services.gradle.org/distributions/gradle-{version}-bin.zip'
        distribution_hash = fetch(distribution+'.sha256').decode().strip()
        jar_hash = fetch(f'https://services.gradle.org/distributions/gradle-{version}-wrapper.jar.sha256').decode().strip()
        tag = version if version.count('.') == 2 else version+'.0'
        jar = fetch(f'https://raw.githubusercontent.com/gradle/gradle/v{tag}/gradle/wrapper/gradle-wrapper.jar')
        assert hashlib.sha256(jar).hexdigest() == jar_hash, 'Upstream wrapper checksum mismatch'
        directory = ROOT / 'gradle/wrappers' / name / 'gradle/wrapper'
        directory.mkdir(parents=True,exist_ok=True)
        (directory / 'gradle-wrapper.jar').write_bytes(jar)
        (directory / 'gradle-wrapper.properties').write_text(f'distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\ndistributionUrl={distribution}\ndistributionSha256Sum={distribution_hash}\nnetworkTimeout=120000\nvalidateDistributionUrl=true\nzipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n',encoding='utf-8')
        result[name] = {'gradle':version,'java':java,'wrapper_sha256':jar_hash}
    atomic_json(ROOT / 'gradle/profiles.json',result)
    root_wrapper = ROOT / 'gradle/wrapper'
    root_wrapper.mkdir(parents=True,exist_ok=True)
    for filename in ('gradle-wrapper.jar','gradle-wrapper.properties'):
        shutil.copyfile(ROOT / 'gradle/wrappers/fabric/gradle/wrapper' / filename,root_wrapper / filename)
    for filename in ('gradlew','gradlew.bat'):
        (ROOT / filename).write_bytes(fetch(f'https://raw.githubusercontent.com/gradle/gradle/v9.6.0/{filename}'))
    for filename in ('LICENSE',):
        (ROOT / 'gradle' / filename).write_bytes(fetch(f'https://raw.githubusercontent.com/gradle/gradle/v9.6.0/{filename}'))
    print('Installed and verified all Gradle wrapper profiles.')

if __name__ == '__main__': install()
