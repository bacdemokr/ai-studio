"""App-open warmup uses actual crew preparation without inference or new grants."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from studio import Studio, Problem
from test_hiring_preparation import ProtectedAdapter


class CrewStartupTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.adapter = ProtectedAdapter()
        self.studio = Studio(folder.name, self.adapter, start_worker=False)
        self.personal = self.studio.session()[0]['id']
        self.owner = self.studio.crew_owner(self.personal)

    def warmup(self):
        return self.studio.prepare_demo(self.owner, {'background': True})

    def run_next(self):
        self.studio.execute(self.studio.next_job())


if __name__ == '__main__':
    unittest.main()
