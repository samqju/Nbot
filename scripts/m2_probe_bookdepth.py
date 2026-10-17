from pathlib import Path
from zipfile import ZipFile
from itertools import islice
p=Path("/root/nbot-v6-m1-20261016/btc-bookdepth-20261001.zip")
with ZipFile(p) as z:
  print("members",z.namelist())
  for row in islice(z.open(z.namelist()[0]),5):
    print(repr(row[:400]))
