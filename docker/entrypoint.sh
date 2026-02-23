#!/bin/sh
# Start backend in a restart loop (so it recovers if it crashes during extraction), then Streamlit.

(
  while true; do
    uvicorn app.main:app --host 0.0.0.0 --port 8000 || true
    echo "Backend exited; restarting in 3s..."
    sleep 3
  done
) &

# Wait for backend to respond (max 30s)
python3 -c "
import time, urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=1)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Backend did not start in time')
"

exec streamlit run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
