# Backend Run Modes

Use `--reload` only during development.

## Development

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

## Normal Run (recommended for regular usage)

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8010
```
