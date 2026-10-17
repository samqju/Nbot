"""Guard against malformed bash in the finite V6 offline research controller."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def test_finite_offline_vps_scripts_parse_in_bash():
    for name in ("m2r_jansep_research_runner.sh","m2r_jansep_vps_sequential_coordinator.sh","m2r_jansep_vps_safe_restart_once.sh"):
        filename=ROOT/"scripts"/name
        run=subprocess.run(["bash","-n",str(filename)],capture_output=True,text=True)
        assert run.returncode==0,(name,run.stderr)
        content=filename.read_text()
        assert "nbot-v6-m1-20261016" in content
        assert "prototype/v6-freqtrade-freqai-20261016" in content
        assert "docker" in content.lower()

def test_finite_research_scripts_do_not_enable_paper_live_or_ordering():
    runner=(ROOT/"scripts/m2r_jansep_research_runner.sh").read_text()
    coordinator=(ROOT/"scripts/m2r_jansep_vps_sequential_coordinator.sh").read_text()
    assert "--network bridge" in runner and "--memory=6g" in runner
    assert "--strategy NbotV6TradeOutcomeFundingResearch" in runner
    assert "--freqaimodel NbotV6PurgedLightGBMRegressor" in runner
    assert 'd["dry_run"] is True' in runner
    assert 'd["exchange"]=={"key":"","secret":""}' in runner
    assert "--network none" in coordinator
    assert "scripts/m2r_jansep_native_rolling_audit.py" in coordinator
    assert "systemctl start" not in runner+coordinator


def test_recovery_requires_native_archive_audit_before_new_systemd():
    script=(ROOT/"scripts/m2r_jansep_vps_safe_restart_once.sh").read_text()
    assert "m2r_jansep_native_rolling_audit.py" in script
    assert "systemd-run" in script
    assert script.index("m2r_jansep_native_rolling_audit.py") < script.index("systemd-run")
    assert "DOCKER_RUNNING" not in script  # no restart without checking docker ps
    assert "docker ps -q" in script
