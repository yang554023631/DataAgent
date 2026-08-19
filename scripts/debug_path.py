import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_dir = script_dir / "../backend"
root_dir = script_dir / ".."

print(f'script_dir: {script_dir.resolve()}')
print(f'root_dir: {root_dir.resolve()}')
print(f'backend_dir: {backend_dir.resolve()}')
print(f'backend_dir exists: {backend_dir.exists()}')
print(f'backend_dir/src exists: {(backend_dir / "src").exists()}')
print(f'backend_dir/src/analysis exists: {(backend_dir / "src" / "analysis").exists()}')
print(f'backend_dir/src/analysis/intent_analyzer.py exists: {(backend_dir / "src" / "analysis" / "intent_analyzer.py").exists()}')
print(f'root_dir/backend/src exists: {(root_dir / "backend" / "src").exists()}')

print(f'\nsys.path after:')
for p in sys.path[:3]:
    print(f'  - {p}')
