"""Paper size names for the grgr pdf commands.

Kept separate from tree_pdf.py so the CLI can list valid choices in --help
without importing reportlab (which is only needed if the 'pdf' extra is installed).
"""

PAPER_SIZE_NAMES = ("A0", "A1", "A2", "A3", "A4", "A5", "letter", "legal", "ledger")
