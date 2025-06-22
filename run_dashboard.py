import uvicorn

if __name__ == "__main__":
    print("Starting Chronos Dashboard...")
    print("Access it at http://127.0.0.1:8000")
    uvicorn.run("chronos.api.main:app", host="127.0.0.1", port=8000, reload=True)