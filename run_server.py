import sys
import os
import uvicorn

port = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('HTTP_PLATFORM_PORT', '8000')

if __name__ == '__main__':
    uvicorn.run("config.asgi:application", host="127.0.0.1", port=int(port), log_level="info")
