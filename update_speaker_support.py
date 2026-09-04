import re

with open('app/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add /speakers endpoint if not present
if "/speakers" not in code:
    speakers_endpoint = """
@app.get("/speakers")
def get_speakers():
    speakers = getattr(tts_engine, "speakers", [])
    return {"speakers": speakers}
"""
    # Insert before process_book or at the end
    code = code.replace("async def process_book", speakers_endpoint + "\n\nasync def process_book")

# 2. Update process_book to accept speaker form param
# Find async def process_book(...)
code = re.sub(
    r'async def process_book\(file: UploadFile = File\(\)\):',
    'async def process_book(file: UploadFile = File(...), speaker: str = Form(None)):',
    code
)

# 3. Update tts_engine.tts_to_file call to use the passed speaker or default
old_tts_call = """        # Modelin desteklediği ilk geçerli hoparlörü dinamik olarak al
        default_speaker = tts_engine.speakers[0] if tts_engine.speakers else None
        
        tts_engine.tts_to_file(
            text=clean_text,
            file_path=mp3_out,
            language="tr",
            speaker=default_speaker
        )"""

new_tts_call = """        # Kullanıcının seçtiği hoparlör veya varsayılan
        selected_speaker = speaker if speaker else (tts_engine.speakers[0] if tts_engine.speakers else None)
        
        tts_engine.tts_to_file(
            text=clean_text,
            file_path=mp3_out,
            language="tr",
            speaker=selected_speaker
        )"""

if old_tts_call in code:
    code = code.replace(old_tts_call, new_tts_call)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("app/main.py güncellendi.")
