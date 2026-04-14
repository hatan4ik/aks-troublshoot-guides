import sys
import os

# Make 'src' importable so tests can do: from k8s_diagnostics.xxx import ...
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
