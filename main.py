import os
import uuid
import threading
import traceback
import torch
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from TTS.api import TTS
import pypdf
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import wave

app = FastAPI()

# Modelin güvenli yüklenmesi için global değişken
tts_model = None

def get_tts_model():
    global tts_model
    if tts_model is None:
        print("Coqui XTTS v2 modeli yükleniyor...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            print("Coqui XTTS v2 modeli başarıyla yüklendi!")
        except Exception as e:
            print(f"Model yüklenirken kritik hata oluştu: {e}")
            traceback.print_exc()
            raise e
    return tts_model

UPLOAD_DIR = "uploads"
AUDIO_DIR = "audio_output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

books_db = []

def extract_text_from_file(file_path: str, filename: str) -> str:
    ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        elif ext == "txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif ext == "epub":
            book = epub.read_epub(file_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    text += soup.get_text() + "\n"
    except Exception as e:
        print(f"Metin çıkarma hatası: {e}")
    
    text = text.strip()
    if not text:
        text = f"Belge içeriği okunamadı: {filename}"
    return text

def split_text_into_chunks(text: str, max_chars: int = 400):
    text = text.replace('\n', ' ')
    words = text.split(' ')
    chunks = []
    current_chunk = ""
    
    for word in words:
        if len(current_chunk) + len(word) + 1 < max_chars:
            current_chunk += (word + " ")
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = word + " "
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return [c for c in chunks if len(c) > 2]

def merge_wav_files(wav_files, output_filename):
    data = []
    for file in wav_files:
        with wave.open(file, 'rb') as w:
            data.append(w.readframes(w.getnframes()))
    
    with wave.open(output_filename, 'wb') as output:
        with wave.open(wav_files[0], 'rb') as w:
            output.setparams(w.getparams())
        for d in data:
            output.writeframes(d)

def process_book_background(file_id: str, file_path: str, filename: str, speaker: str):
    output_audio_path = os.path.join(AUDIO_DIR, f"{file_id}.wav")
    try:
        print(f"Arka plan işlemi başladı: {filename}")
        model = get_tts_model()
        
        extracted_text = extract_text_from_file(file_path, filename)
        chunks = split_text_into_chunks(extracted_text, max_chars=400)
        temp_wavs = []
        
        target_speaker = speaker if speaker else (model.speakers[0] if hasattr(model, 'speakers') and model.speakers else "Ana Florence")
        
        for i, chunk in enumerate(chunks):
            temp_chunk_path = os.path.join(UPLOAD_DIR, f"{file_id}_part_{i}.wav")
            model.tts_to_file(
                text=chunk,
                speaker=target_speaker,
                language="tr",
                file_path=temp_chunk_path
            )
            temp_wavs.append(temp_chunk_path)
            
        if temp_wavs:
            merge_wav_files(temp_wavs, output_audio_path)
            for tw in temp_wavs:
                if os.path.exists(tw):
                    os.remove(tw)
                    
        for book in books_db:
            if book["id"] == file_id:
                book["has_audio"] = True
                book["audio_url"] = f"/audio/{file_id}.wav"
                break
        print(f"Arka plan işlemi başarıyla tamamlandı: {filename}")
    except Exception as e:
        print(f"KRİTİK HATA - Arka plan ses sentezleme başarısız ({filename}):")
        traceback.print_exc()
        for book in books_db:
            if book["id"] == file_id:
                book["has_audio"] = False
                book["audio_url"] = ""
                break

@app.get("/speakers", response_class=JSONResponse)
def get_speakers():
    try:
        model = get_tts_model()
        speakers = model.speakers if hasattr(model, 'speakers') and model.speakers else []
        return {"speakers": speakers}
    except Exception as e:
        print(f"Konuşmacılar alınırken hata: {e}")
        return {"speakers": []}

@app.get("/books", response_class=JSONResponse)
def get_books():
    return books_db

@app.post("/process", response_class=JSONResponse)
async def process_document(file: UploadFile = File(...), speaker: str = Form(None)):
    file_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
         
    book_info = {
        "id": file_id,
        "name": file.filename,
        "has_audio": False,
        "audio_url": ""
    }
    books_db.append(book_info)
    
    thread = threading.Thread(target=process_book_background, args=(file_id, file_path, file.filename, speaker))
    thread.daemon = True
    thread.start()
    
    return {"status": "success", "book": book_info}

@app.delete("/delete/{book_id}", response_class=JSONResponse)
def delete_book(book_id: str):
    global books_db
    books_db = [b for b in books_db if b["id"] != book_id]
    return {"status": "deleted"}

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Doc Reader Pro (Türkçe XTTS v2)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121212; color: #e0e0e0; margin: 0; padding: 40px; display: flex; flex-direction: column; align-items: center; }
        .container { width: 100%; max-width: 800px; background: #1e1e1e; padding: 30px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
        h1 { font-size: 24px; margin-bottom: 20px; color: #fff; text-align: center; }
        .upload-box { display: flex; flex-direction: column; gap: 15px; margin-bottom: 30px; border: 2px dashed #333; padding: 20px; border-radius: 8px; background: #252525; }
        input[type="file"], select { padding: 10px; border-radius: 6px; background: #1e1e1e; color: #fff; border: 1px solid #444; font-size: 14px; }
        label { font-size: 14px; color: #a78bfa; font-weight: bold; margin-top: 5px; display: block; }
        button { background: #7c3aed; color: white; border: none; padding: 12px 20px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #6d28d9; }
        button:disabled { background: #4b5563; cursor: not-allowed; }
        #loading { display: none; text-align: center; color: #a78bfa; font-weight: bold; margin-top: 15px; }
        .books-list { margin-top: 20px; }
        .book-item { background: #2a2a2a; padding: 15px; border-radius: 6px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .book-actions { display: flex; gap: 10px; align-items: center; }
        audio { height: 35px; }
        .delete-btn { background: #dc2626; padding: 6px 12px; font-size: 14px; }
        .delete-btn:hover { background: #b91c1c; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Doc Reader Pro (Türkçe XTTS v2)</h1>
        
        <div class="upload-box">
            <label for="fileInput">Kitap veya Belge Seçin (.pdf, .txt, .epub):</label>
            <input type="file" id="fileInput" style="width: 100%; margin-top: 5px; margin-bottom: 15px;">
            
            <label for="speakerSelect">Ses Profili (Konuşmacı Seçimi):</label>
            <select id="speakerSelect" style="width: 100%; margin-top: 5px; margin-bottom: 20px;">
                <option value="">Yükleniyor...</option>
            </select>

            <button type="button" id="submitBtn" onclick="handleUpload()" style="width: 100%;">Kitabı Yükle ve Sese Dönüştür</button>
            <div id="loading">⏳ Belge kuyruğa eklendi. Arka planda seslendiriliyor, sayfayı yenileyerek durumu takip edebilirsiniz.</div>
        </div>

        <div class="books-list">
            <h2>Kitaplarım</h2>
            <div id="booksContainer">
                <p style="color: #888;">Yükleniyor...</p>
            </div>
        </div>
    </div>

    <script>
        async function fetchSpeakers() {
            const select = document.getElementById('speakerSelect');
            try {
                const response = await fetch('/speakers');
                const data = await response.json();
                select.innerHTML = '';
                
                if (data.speakers && data.speakers.length > 0) {
                    data.speakers.forEach(speaker => {
                        const option = document.createElement('option');
                        option.value = speaker;
                        option.textContent = speaker;
                        select.appendChild(option);
                    });
                } else {
                    select.innerHTML = '<option value="">Varsayılan Ses</option>';
                }
            } catch (err) {
                console.error('Konuşmacılar yüklenemedi:', err);
                select.innerHTML = '<option value="Ana Florence">Ana Florence (Varsayılan)</option>';
            }
        }

        async function fetchBooks() {
            try {
                const response = await fetch('/books');
                const books = await response.json();
                const container = document.getElementById('booksContainer');
                container.innerHTML = '';
                
                if (books.length === 0) {
                    container.innerHTML = '<p style="color: #888;">Henüz yüklenmiş bir kitap yok.</p>';
                    return;
                }

                books.forEach(book => {
                    const div = document.createElement('div');
                    div.className = 'book-item';
                    div.innerHTML = `
                        <div>
                            <strong>${book.name}</strong><br>
                            <small style="color: #888;">ID: ${book.id}</small>
                        </div>
                        <div class="book-actions">
                            ${book.has_audio ? `<audio controls src="${book.audio_url}"></audio>` : '<span style="color: #f59e0b;">⏳ Ses hazırlanıyor (Arka planda işleniyor)...</span>'}
                            <button class="delete-btn" onclick="deleteBook('${book.id}')">Sil</button>
                        </div>
                    `;
                    container.appendChild(div);
                });
            } catch (err) {
                console.error('Kitaplar yüklenirken hata oluştu:', err);
            }
        }

        async function handleUpload() {
            const fileInput = document.getElementById('fileInput');
            const speakerSelect = document.getElementById('speakerSelect');
            const submitBtn = document.getElementById('submitBtn');
            const loadingDiv = document.getElementById('loading');

            if (fileInput.files.length === 0) {
                alert('Lütfen bir dosya seçin.');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('speaker', speakerSelect.value);

            submitBtn.disabled = true;
            loadingDiv.style.display = 'block';

            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    fileInput.value = '';
                    await fetchBooks();
                } else {
                    alert('İşlem sırasında bir hata oluştu.');
                }
            } catch (err) {
                console.error('Yükleme hatası:', err);
                alert('Sunucuya bağlanırken hata oluştu.');
            } finally {
                submitBtn.disabled = false;
                setTimeout(() => { loadingDiv.style.display = 'none'; }, 5000);
            }
        }

        async function deleteBook(id) {
            if (!confirm('Bu kitabı silmek istediğinize emin misiniz?')) return;
            try {
                await fetch(`/delete/${id}`, { method: 'DELETE' });
                await fetchBooks();
            } catch (err) {
                console.error('Silme hatası:', err);
            }
        }

        fetchSpeakers();
        fetchBooks();
        setInterval(fetchBooks, 10000);
    </script>
</body>
</html>
"""
