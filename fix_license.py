with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Coqui modelinin lisans şartını otomatik onaylamak için environment değişkeni ekliyoruz
license_fix = """
import os
os.environ["COQUI_TOS_AGREED"] = "1"

from TTS.api import TTS
"""

content = content.replace("from TTS.api import TTS", license_fix)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Lisans otomatik onaylama eklendi.")
