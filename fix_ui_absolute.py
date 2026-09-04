import re

with open('app/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

html_content = """<!DOCTYPE html>
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
            <div id="loading">⏳ Kitap yükleniyor ve XTTS v2 ile sese dönüştürülüyor, lütfen bekleyin... (Bu işlem birkaç dakika sürebilir)</div>
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
                            ${book.has_audio ? `<audio controls src="${book.audio_url}"></audio>` : '<span style="color: #f59e0b;">Ses hazırlanıyor</span>'}
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
                loadingDiv.style.display = 'none';
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
    </script>
</body>
</html>"""

new_route = f'''@app.get("/", response_class=HTMLResponse)
def read_root():
    return """{html_content}"""
'''

code = re.sub(r'@app\.get\("/"\)[^@]*', new_route, code, flags=re.DOTALL)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("main.py güncellendi.")
