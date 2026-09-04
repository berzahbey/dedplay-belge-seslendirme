# -*- coding: utf-8 -*-
import os
import re
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from TTS.api import TTS
from pydub import AudioSegment

os.makedirs("/app/books", exist_ok=True)
os.makedirs("/output", exist_ok=True)

app = FastAPI()
app.mount("/output", StaticFiles(directory="/output"), name="output")

model = None
active_jobs = set()

def get_tts_model():
    global model
    if model is None:
        print("Coqui XTTS v2 modeli yükleniyor...")
        device = "cpu"
        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        print("Coqui XTTS v2 modeli başarıyla yüklendi!")
    return model

default_speaker = "Damien Black"  # Türkçe için desteklenen erkek ses profili

def split_text(text, max_length=200):
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        clean_s = sentence.strip()
        if not clean_s or (clean_s.isdigit() or len(clean_s) <= 2 and not clean_s.isalnum()):
            continue
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def process_book_background(filename: str, speaker: str):
    active_jobs.add(filename)
    try:
        tts_model = get_tts_model()
        pdf_path = os.path.join("/app/books", filename)
        base_name = os.path.splitext(filename)[0]
        output_wav = os.path.join("/output", f"{base_name}.wav")
        print(f"Arka plan işlem başladı: {filename} (Ses: {speaker})")
        
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + " "
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        text_chunks = split_text(full_text, max_length=180)
        temp_chunk_files = []
        
        for i, chunk in enumerate(text_chunks):
            if not chunk:
                continue
            chunk_path = f"/tmp/chunk_{i}_{os.getpid()}.wav"
            success = False
            speakers_to_try = [speaker, "Damien Black", "Andrew Chipper", "Ana Florence"]
            for s in speakers_to_try:
                try:
                    tts_model.tts_to_file(
                        text=chunk, 
                        file_path=chunk_path, 
                        speaker=s, 
                        language="tr"
                    )
                    if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                        success = True
                        break
                except Exception:
                    continue
            
            if success:
                temp_chunk_files.append(chunk_path)
            else:
                print(f"Parça işlenemedi ve atlandı: {chunk[:30]}...")
        
        if not temp_chunk_files:
            print("HATA: Hiçbir ses parçası üretilemedi!")
            return

        combined_audio = AudioSegment.empty()
        for file_path in temp_chunk_files:
            try:
                segment = AudioSegment.from_wav(file_path)
                combined_audio += segment
                os.remove(file_path)
            except Exception as seg_err:
                print(seg_err)
        
        combined_audio.export(output_wav, format="wav")
        print(f"Tamamlandı ve birleştirildi: {output_wav}")
    except Exception as e:
        print(f"HATA: {e}")
    finally:
        active_jobs.discard(filename)

@app.get("/", response_class=HTMLResponse)
def read_root():
    return f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Doc Reader Pro - Sesli Kitap Dönüştürücü</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 950px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
            .section {{ margin-bottom: 30px; padding: 20px; background: #fafafa; border: 1px solid #e1e4e8; border-radius: 8px; }}
            h3 {{ margin-top: 0; color: #34495e; }}
            input[type="file"] {{ width: 100%; padding: 10px; margin: 10px 0 20px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
            button {{ background-color: #3498db; color: white; border: none; padding: 10px 15px; font-size: 14px; border-radius: 6px; cursor: pointer; }}
            button:hover {{ opacity: 0.9; }}
            .btn-primary {{ background-color: #3498db; width: 100%; padding: 12px; font-size: 16px; }}
            .btn-danger {{ background-color: #e74c3c; }}
            .btn-success {{ background-color: #27ae60; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; }}
            audio {{ width: 100%; max-width: 220px; }}
            .status-ready {{ color: #27ae60; font-weight: bold; }}
            .status-processing {{ color: #e67e22; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📚 Doc Reader Pro (XTTS v2)</h1>
            <div class="section">
                <h3>1. Yeni PDF Kitap Yükle</h3>
                <form id="uploadForm" enctype="multipart/form-data">
                    <input type="file" id="pdfFile" name="file" accept=".pdf" required>
                    <button type="submit" class="btn-primary">Kitabı Yükle</button>
                </form>
            </div>
            <div class="section">
                <h3>2. Kitaplarım ve Seslendirme Durumu</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Kitap Adı</th>
                            <th>Ses Profili</th>
                            <th>Durum / İşlem</th>
                            <th>Ses Dosyası</th>
                            <th>Sil</th>
                        </tr>
                    </thead>
                    <tbody id="bookTableBody">
                        <tr><td colspan="5" style="text-align:center;">Yükleniyor...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            async function loadBooks() {{
                try {{
                    const res = await fetch('/books');
                    const books = await res.json();
                    const tbody = document.getElementById('bookTableBody');
                    tbody.innerHTML = '';
                    if (books.length === 0) {{
                        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Henüz hiç PDF yüklenmemiş.</td></tr>';
                        return;
                    }}
                    for (let book of books) {{
                        let tr = document.createElement('tr');
                        
                        let tdName = document.createElement('td');
                        tdName.innerText = book.filename;
                        tr.appendChild(tdName);

                        let tdSpeaker = document.createElement('td');
                        tdSpeaker.innerText = "{default_speaker}";
                        tr.appendChild(tdSpeaker);

                        let tdAction = document.createElement('td');
                        if (book.processing) {{
                            tdAction.innerHTML = `<span class="status-processing">⏳ İşleniyor...</span>`;
                        }} else if (book.ready) {{
                            tdAction.innerHTML = `<span class="status-ready">✔ Hazır</span>`;
                        }} else {{
                            let btnProcess = document.createElement('button');
                            btnProcess.className = "btn-success";
                            btnProcess.innerText = "Seslendir";
                            btnProcess.onclick = () => startProcess(book.filename);
                            tdAction.appendChild(btnProcess);
                        }}
                        tr.appendChild(tdAction);

                        let tdAudio = document.createElement('td');
                        if (book.ready) {{
                            tdAudio.innerHTML = `<audio controls src="${{book.audio_url}}"></audio><br><a href="${{book.audio_url}}" download style="font-size:12px;">İndir</a>`;
                        }} else {{
                            tdAudio.innerText = '-';
                        }}
                        tr.appendChild(tdAudio);

                        let tdDelete = document.createElement('td');
                        let btnDelete = document.createElement('button');
                        btnDelete.className = "btn-danger";
                        btnDelete.innerText = "Sil";
                        btnDelete.onclick = () => deleteBook(book.filename);
                        tdDelete.appendChild(btnDelete);
                        tr.appendChild(tdDelete);

                        tbody.appendChild(tr);
                    }}
                }} catch (e) {{ console.error(e); }}
            }}

            document.getElementById('uploadForm').onsubmit = async (e) => {{
                e.preventDefault();
                const formData = new FormData();
                formData.append("file", document.getElementById('pdfFile').files[0]);
                const btn = e.target.querySelector('button');
                btn.innerText = "Yükleniyor...";
                const res = await fetch('/upload', {{ method: 'POST', body: formData }});
                if (res.ok) {{
                    document.getElementById('uploadForm').reset();
                    loadBooks();
                }}
                btn.innerText = "Kitabı Yükle";
            }};

            async function startProcess(filename) {{
                const res = await fetch('/process', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ filename: filename, speaker: "{default_speaker}" }})
                }});
                if (res.ok) {{
                    loadBooks();
                }}
            }}

            async function deleteBook(filename) {{
                if (!confirm(`"${{filename}}" kitabını ve ilişkili ses dosyasını silmek istediğinize emin misiniz?`)) return;
                const res = await fetch('/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ filename: filename }})
                }});
                if (res.ok) {{
                    loadBooks();
                }} else {{
                    alert("Silme işlemi başarısız oldu.");
                }}
            }}

            window.onload = async () => {{ await loadBooks(); setInterval(loadBooks, 4000); }};
        </script>
    </body>
    </html>
    """

@app.get("/books")
def list_books():
    books = []
    if os.path.exists("/app/books"):
        for f in os.listdir("/app/books"):
            if f.endswith(".pdf"):
                base_name = os.path.splitext(f)[0]
                wav_name = f"{base_name}.wav"
                wav_path = os.path.join("/output", wav_name)
                wav_exists = os.path.exists(wav_path)
                is_processing = f in active_jobs
                books.append({
                    "filename": f,
                    "ready": wav_exists,
                    "processing": is_processing,
                    "audio_url": f"/output/{wav_name}" if wav_exists else None
                })
    return books

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    file_path = os.path.join("/app/books", file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return {"status": "success", "filename": file.filename}

class ProcessRequest(BaseModel):
    filename: str
    speaker: str = default_speaker

@app.post("/process")
def process_book(req: ProcessRequest, background_tasks: BackgroundTasks):
    if req.filename in active_jobs:
        return {"status": "already_processing"}
    pdf_path = os.path.join("/app/books", req.filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Kitap bulunamadi.")
    background_tasks.add_task(process_book_background, req.filename, req.speaker)
    return {"status": "started", "filename": req.filename}

@app.post("/delete")
def delete_book(req: ProcessRequest):
    pdf_path = os.path.join("/app/books", req.filename)
    base_name = os.path.splitext(req.filename)[0]
    wav_path = os.path.join("/output", f"{base_name}.wav")
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return {"status": "success", "filename": req.filename}
