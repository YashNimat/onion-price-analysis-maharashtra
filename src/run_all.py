"""Run the whole pipeline: ingest -> SQL analysis -> forecast -> Excel.

    python src/run_all.py            # real data in data/raw
    python src/run_all.py --demo     # synthetic data, to test the pipeline end to end
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
demo = "--demo" in sys.argv


def run(script, *args):
    print(f"\n>>> {script} {' '.join(args)}")
    subprocess.run([sys.executable, str(SRC / script), *args], check=True, cwd=SRC)


if demo:
    run("synthetic.py")
run("ingest.py", *(["--include-synthetic"] if demo else []))
run("run_sql.py")
run("forecast.py")
run("arrivals_analysis.py")
run("hold_vs_sell.py")
run("build_excel.py", *(["--demo"] if demo else []))
print("\nDone. Next: load data/processed/*.csv into Power BI (see powerbi/BUILD_GUIDE.md).")
