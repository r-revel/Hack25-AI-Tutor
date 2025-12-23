Generate the requirements.txt File
pip freeze > requirements.txt

запуск проект

```bash

python3 -m venv ./venv
source .venv/bin/activate #для винды .\.venv\Scripts\Activate.ps1
# install
pip install -r requirements.txt
# Запускаем в папки ./rest-api/src/
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
```


docker build -t ollama-api .

docker run -d -p 8000:8000 --name ollama-container-api ollama-api


# Установите pandas
pip install langchain_huggingface

# Обновите requirements.txt
pip freeze | grep langchain-huggingface >> requirements.txt


## Запуск
1. Создать эмбеддинги
```bash
python build_index.py --input ../../Notebooks/cloud_ru_docs.jsonl --persist_dir chroma_db
```