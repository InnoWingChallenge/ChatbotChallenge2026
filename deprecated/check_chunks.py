import json
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
p = Path('data.json')
print('exists', p.exists())
docs = json.loads(p.read_text(encoding='utf-8'))
print('docs', len(docs))
splitter = RecursiveCharacterTextSplitter(chunk_size=300, length_function=len, separators=[''])
total = 0
for i, d in enumerate(docs[:20], 1):
    text = d.get('text', '').strip()
    chunks = list(splitter.split_text(text))
    print(i, 'len', len(text), 'chunks', len(chunks))
    total += len(chunks)
print('total_chunks_first20', total)
