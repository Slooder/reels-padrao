"""Suítes do kit: rode a partir de kit/ com `python3 -m unittest` (ou `python3 -m unittest testes.test_da -v`)."""
import os
import shutil
import sys

sys.dont_write_bytecode = True      # as suítes não deixam __pycache__ dentro da skill (D9)
shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__"), ignore_errors=True)
