"""Integration checks for template validation and customization in an isolated copy."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from template import ROOT, properties

class TemplateToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copy = ROOT.parent / (ROOT.name+'-support') / 'tests' / uuid.uuid4().hex
        cls.copy.mkdir(parents=True)
        paths = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
        for relative in filter(None,paths):
            source = ROOT / relative
            destination = cls.copy / relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)

    def run_tool(self, tool, *args):
        return subprocess.run([sys.executable,str(self.copy / 'tools/kyro' / tool),*args],cwd=self.copy,capture_output=True,text=True)

    def test_customization_and_validation(self):
        result = self.run_tool('customize.py','--id','samplemod','--group','org.sample','--name','Sample Mod')
        self.assertEqual(0,result.returncode,result.stderr)
        result = self.run_tool('template.py','validate')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertTrue((self.copy / 'common/src/main/java/org/sample/samplemod/TemplateMod.java').is_file())
        self.assertIn('Sample Mod initialized',(self.copy / 'common/src/main/java/org/sample/samplemod/TemplateMod.java').read_text())
        data = json.loads((self.copy / 'versions/26.3/fabric/src/main/resources/fabric.mod.json').read_text())
        self.assertEqual(['org.sample.samplemod.fabric.Entrypoint'],data['entrypoints']['main'])

    def test_invalid_id_rejected(self):
        result = self.run_tool('customize.py','--id','../escape','--group','org.sample','--name','Sample')
        self.assertNotEqual(0,result.returncode)

    def test_overlapping_mod_ids_are_not_replaced_twice(self):
        metadata = properties(self.copy / 'properties/mod.properties')
        mod_id = metadata['mod.id']+'plus'
        result = self.run_tool('customize.py','--id',mod_id,'--group',metadata['mod.group'],'--name','Renamed Mod')
        self.assertEqual(0,result.returncode,result.stderr)
        result = self.run_tool('template.py','validate')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

if __name__ == '__main__': unittest.main()
