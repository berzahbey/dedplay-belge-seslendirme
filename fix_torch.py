with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Torch safe globals ekleme
target = 'tts_engine = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)'
replacement = """
import torch
from TTS.tts.configs.xtts_config import XttsConfig
try:
    torch.serialization.add_safe_globals([XttsConfig])
except AttributeError:
    pass

tts_engine = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
"""

content = content.replace(target, replacement)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Torch safe globals eklendi.")
