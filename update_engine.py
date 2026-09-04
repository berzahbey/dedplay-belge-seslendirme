import re

with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Kokoro import ve pipeline başlatma kodlarını Coqui TTS ile değiştiriyoruz
old_init_pattern = re.compile(r'from kokoro import KPipeline.*?\n', re.DOTALL)
content = old_init_pattern.sub('from TTS.api import TTS\n', content)

# Pipeline tanımlarını XTTS v2 ile değiştir
content = content.replace("KPipeline(lang_code='z')", "TTS('tts_models/multilingual/multi-dataset/xtts_v2', gpu=False)")
content = content.replace("KPipeline(lang_code='a')", "TTS('tts_models/multilingual/multi-dataset/xtts_v2', gpu=False)")
content = content.replace("KPipeline(lang_code='tr')", "TTS('tts_models/multilingual/multi-dataset/xtts_v2', gpu=False)")

# Ses sentezleme (generate) fonksiyonunu XTTS yapısına uyarlayalım
# XTTS v2 kullanımı: tts.tts_to_file(text=chunk, speaker_wav="path/to/reference.wav", language="tr", file_path=output_path)
print("Güncelleme betiği hazırlandı.")
