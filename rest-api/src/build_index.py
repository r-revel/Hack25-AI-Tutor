import json
import argparse
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings
import os
import uuid
import torch




def clean_text(t: str) -> str:
    # простая очистка — можно расширить
    t = t.replace('\xa0', ' ')
    import re
    t = re.sub(r"\n{2,}", "\n\n", t)
    t = re.sub(r"#", "", t)
    t = t.strip()
    return t




def build_index(input_path: str, persist_dir: str):
    print('Load model...')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    emb_model = SentenceTransformer('intfloat/multilingual-e5-large', device=device)

    print('Init chroma...')
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name='cloud_docs')

    with open(input_path, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f if line.strip()]


    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". "]
    )

    added = 0
    for rec in data:
        content = rec.get('content') or ''
        title = rec.get('title') or ''
        url = rec.get('url') or ''
        section = rec.get('section') or ''
        source = rec.get('source') or ''
        timestamp = rec.get('timestamp') or ''

        text = clean_text(content)
        chunks = splitter.split_text(text)

        for idx, chunk in enumerate(chunks):
            doc_id = f"{uuid.uuid4()}"
            metadata = {
                'url': url,
                'title': title,
                'section': section,
                'source': source,
                'timestamp': timestamp,
                'chunk_id': idx,
                'total_chunks': len(chunks)
            }
            emb = emb_model.encode(chunk).tolist()
            try:
                collection.add(
                    documents=[chunk],
                    embeddings=[emb],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                added += 1
            except Exception as e:
                print('Add error', e)


    print(f'Added {added} chunks to Chroma at {persist_dir}')




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--persist_dir', default='./db')
    args = parser.parse_args()
    os.makedirs(args.persist_dir, exist_ok=True)
    build_index(args.input, args.persist_dir)