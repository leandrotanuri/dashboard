import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import requests
from dotenv import load_dotenv
from sheets_client import read_range
load_dotenv()

SHEET = "1S6FUTqK7kDG9ZOgmuakLdxRCSrMxRbegKIEdwCJjS68"
tab   = "\U0001f4c8 Jun"
rows  = read_range(SHEET, f"'{tab}'!M5:N35")

total_inv, total_seg = 0.0, 0
for i, row in enumerate(rows):
    inv = row[0] if len(row) > 0 else ""
    seg = row[1] if len(row) > 1 else ""
    if inv:
        try: total_inv += float(str(inv).replace(",", ".").replace("R$", "").strip())
        except: pass
    if seg:
        try: total_seg += int(float(str(seg).replace(",", ".")))
        except: pass

print(f"Total invest seg (sem imp): R$ {total_inv:.2f}")
print(f"Total seguidores: {total_seg}")
if total_seg > 0:
    custo_sem = total_inv / total_seg
    custo_com = total_inv * 1.1385 / total_seg
    print(f"Custo/seg sem imp: R$ {custo_sem:.2f}")
    print(f"Custo/seg com imp: R$ {custo_com:.2f}")
