import tempfile
import unittest
from pathlib import Path

from skynet.lab import AdaptiveLab
from skynet.routing import ModelRouter
from skynet.sandbox import CandidateSandbox
from skynet.telemetry import ModelTelemetryStore


class AdaptiveLabTests(unittest.TestCase):
    def test_static_lab_job_never_executes_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sandbox = CandidateSandbox(root / "candidates")
            sandbox.stage("candidate-one", "skill", "# Skill\nSafe proposal only")
            lab = AdaptiveLab(root / "lab", root / "candidates")
            job = lab.prepare("candidate-one", "static-only")
            self.assertEqual(job.backend, "static-only")
            self.assertIn("no candidate code was executed", lab.launch(job.job_id).lower())

    def test_candidate_path_cannot_escape_lab(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lab = AdaptiveLab(root / "lab", root / "candidates")
            with self.assertRaises((ValueError, FileNotFoundError)):
                lab.prepare("../escape", "static-only")


class AdaptiveRoutingTests(unittest.TestCase):
    def test_measured_quality_can_outweigh_default_bias(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = ModelTelemetryStore(Path(tmp) / "telemetry.db")
            try:
                quality = {
                    "base:8b": {"mean_score": 0.30, "pass_rate": 0.30, "safety_failures": 0},
                    "better:8b": {"mean_score": 1.00, "pass_rate": 1.00, "safety_failures": 0},
                }
                router = ModelRouter(
                    "http://127.0.0.1:11434",
                    "base:8b",
                    ["base:8b", "better:8b"],
                    telemetry=telemetry,
                    quality_lookup=lambda name: quality.get(name),
                )
                decision = router.decide("analyse cette architecture", ["base:8b", "better:8b"])
                self.assertEqual(decision.model, "better:8b")
            finally:
                telemetry.close()

    def test_telemetry_persists_ram_vram_and_energy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ModelTelemetryStore(Path(tmp) / "telemetry.db")
            try:
                store.record("m:1", "general", 2.0, energy_wh=0.02, gpu_memory_mb=4096, ram_delta_mb=512)
                stats = store.stats("m:1", "general")
                self.assertIsNotNone(stats)
                self.assertEqual(stats.samples, 1)
                self.assertEqual(stats.avg_gpu_memory_mb, 4096)
                self.assertEqual(stats.avg_ram_delta_mb, 512)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
