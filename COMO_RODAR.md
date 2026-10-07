# Como rodar o Orus Quant localmente

São 2 terminais: um para o backend, outro para o frontend.

## Pré-requisitos

- Python 3.12+ (backend)
- Node.js 22+ e npm (frontend)

## 1. Backend (terminal 1)

```powershell
cd "C:\Users\Gabriel\Desktop\Orus Quant\backend"
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Se `uvicorn` não for reconhecido:

```powershell
python -m uvicorn main:app --port 8000
```

API no ar em: http://127.0.0.1:8000 (`/health` deve responder `{"status":"ok"}`).

## 2. Frontend (terminal 2)

```powershell
cd "C:\Users\Gabriel\Desktop\Orus Quant\frontend"
npm install
npm run dev
```

Página no ar em: http://127.0.0.1:5173

> O Vite redireciona `/api` para o backend automaticamente, por isso o
> backend precisa estar rodando na porta 8000 antes de abrir a página.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Falha ao carregar sinais` na página | Backend parado | Suba o backend (terminal 1) e recarregue |
| `EADDRINUSE` / porta em uso | Processo antigo preso | Feche o terminal do processo ou troque a porta (`--port 8001`) |
| Página em branco | Erro de JS no navegador | Abra o DevTools (F12) → Console e veja o erro |
| `uvicorn` não reconhecido | Script fora do PATH | Use `python -m uvicorn main:app --port 8000` |
