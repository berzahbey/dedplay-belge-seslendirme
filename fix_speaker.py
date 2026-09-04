with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Eski hatalı tts_to_file çağrısını bul ve dinamik speaker seçimi ile değiştir
old_block = """    # Coqui XTTS v2 ile Türkçe ses sentezleme
    try:
        # Varsayılan referans ses ile Türkçe üretim (veya modelsiz yerleşik hoparlör)
        tts_engine.tts_to_file(
            text=clean_text,
            file_path=mp3_out,
            language="tr",
            speaker="Ana_Default" # XTTS varsayılan hoparlör profili
        )"""

new_block = """    # Coqui XTTS v2 ile Türkçe ses sentezleme
    try:
        # Modelin desteklediği ilk geçerli hoparlörü dinamik olarak al
        default_speaker = tts_engine.speakers[0] if tts_engine.speakers else None
        
        tts_engine.tts_to_file(
            text=clean_text,
            file_path=mp3_out,
            language="tr",
            speaker=default_speaker
        )"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('app/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Speaker kodu güncellendi.")
else:
    print("Eşleşme bulunamadı, lütfen manuel kontrol edin.")
